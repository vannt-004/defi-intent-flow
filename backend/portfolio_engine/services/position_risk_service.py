import math
import statistics
from datetime import datetime, timezone

from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_risk_snapshot_repository import PositionRiskSnapshotRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository


class PositionRiskService:
    HISTORY_DAYS = 30

    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)
        self.portfolio_repository = PortfolioRepository(self.db)
        self.position_snapshot_repository = PositionSnapshotRepository(self.db)
        self.risk_snapshot_repository = PositionRiskSnapshotRepository(self.db)

    def get_wallet_risk(self, wallet: str, persist: bool = False) -> dict:
        wallet = wallet.lower()
        latest_portfolio = self.portfolio_repository.get_latest_snapshot(wallet) or {}
        positions = self.position_snapshot_repository.get_latest_wallet_positions(wallet)
        lending_context = self._build_lending_context(positions)

        position_risks = []
        for position in positions:
            if position.get("type") == "amm":
                position_risks.append(self._analyze_lp_position(wallet, position))
            else:
                position_risks.append(self._analyze_lending_position(wallet, position, lending_context))

        portfolio = self._aggregate(position_risks, latest_portfolio)

        result = {
            "wallet": wallet,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "portfolio": portfolio,
            "positions": position_risks,
        }
        if persist:
            self._persist(result)
        return result

    def get_portfolio_risk_history(self, wallet: str, limit: int = 90) -> list[dict]:
        rows = self.risk_snapshot_repository.get_portfolio_risk_history(wallet.lower(), limit=limit)
        return [
            {
                "timestamp": row.get("timestamp"),
                "riskScore": row.get("risk_score"),
                "riskLevel": row.get("risk_level"),
                **(row.get("payload") or {}),
            }
            for row in rows
        ]

    def _build_lending_context(self, positions: list[dict]) -> dict:
        collateral_positions = [
            p for p in positions
            if p.get("side") in ("LENDER", "COLLATERAL") and p.get("type") != "amm"
        ]
        borrow_positions = [
            p for p in positions
            if p.get("side") == "BORROWER" and p.get("type") != "amm"
        ]
        weighted_collateral = 0.0
        collateral_usd = 0.0
        debt_usd = 0.0
        missing_threshold_positions = []

        for position in collateral_positions:
            value = float(position.get("value_usd") or 0)
            liquidation_threshold = float(position.get("liquidation_threshold") or 0)
            collateral_usd += value
            if liquidation_threshold <= 0:
                missing_threshold_positions.append(position.get("position_id"))
                continue
            weighted_collateral += value * liquidation_threshold

        for position in borrow_positions:
            debt_usd += float(position.get("value_usd") or 0)

        health_factor = weighted_collateral / debt_usd if debt_usd > 0 and weighted_collateral > 0 else (999.0 if debt_usd <= 0 else None)
        liquidation_buffer = weighted_collateral - debt_usd

        return {
            "collateral_usd": collateral_usd,
            "debt_usd": debt_usd,
            "weighted_collateral_usd": weighted_collateral,
            "health_factor": health_factor,
            "liquidation_buffer_usd": liquidation_buffer,
            "missing_threshold_positions": missing_threshold_positions,
        }

    def _analyze_lending_position(self, wallet: str, position: dict, context: dict) -> dict:
        symbol = position.get("symbol")
        side = position.get("side")
        value_usd = float(position.get("value_usd") or 0)
        price_stats = self._price_stats([symbol]).get(symbol, self._empty_price_stats(symbol))
        health_factor = context["health_factor"]
        liquidation_threshold = float(position.get("liquidation_threshold") or 0)
        weighted_collateral = context["weighted_collateral_usd"]
        debt_usd = context["debt_usd"]

        price_move_to_liquidation = None
        if side in ("LENDER", "COLLATERAL") and value_usd > 0 and debt_usd > 0:
            collateral_contribution = value_usd * liquidation_threshold
            if collateral_contribution > 0:
                price_move_to_liquidation = (weighted_collateral - debt_usd) / collateral_contribution * 100
        elif side == "BORROWER" and value_usd > 0 and debt_usd > 0:
            if weighted_collateral > debt_usd:
                price_move_to_liquidation = (weighted_collateral / debt_usd - 1) * (debt_usd / value_usd) * 100
            else:
                price_move_to_liquidation = 0.0

        forecast_risk_pct = self._liquidation_probability(side, price_move_to_liquidation, price_stats)
        signals = []
        score = 12.0

        if debt_usd > 0 and liquidation_threshold <= 0 and side in ("LENDER", "COLLATERAL"):
            score += 22
            signals.append("Missing protocol liquidation threshold for this collateral; risk model confidence is reduced")

        if health_factor is not None and health_factor != 999:
            if health_factor <= 1:
                score += 65
                signals.append("Current weighted collateral is below debt; liquidation can happen now")
            elif price_move_to_liquidation is not None:
                buffer_component = max(0.0, min(45.0, 45.0 * (1 - min(price_move_to_liquidation, 50.0) / 50.0)))
                score += buffer_component
                if price_move_to_liquidation < abs(price_stats.get("forecast_7d_pct") or 0) + price_stats.get("volatility_30d_pct", 0):
                    signals.append("7 day forecast plus volatility can consume liquidation buffer")

        if side in ("LENDER", "COLLATERAL"):
            if price_stats["trend"] == "DOWN":
                score += 12
                signals.append("Collateral token trend is down based on recent price history")
        elif side == "BORROWER":
            if price_stats["trend"] == "UP":
                score += 12
                signals.append("Borrowed token trend is up, increasing debt value risk")

        if forecast_risk_pct > 35:
            score += min(25, forecast_risk_pct / 2)
            signals.append("Forecast model shows elevated probability of touching liquidation conditions")

        if price_stats["volatility_30d_pct"] > max(abs(price_stats["forecast_7d_pct"]), 1) * 1.5:
            score += 8
            signals.append("High volatility makes the forecast less stable")

        score = self._clamp(score, 0, 100)

        return {
            "positionId": position.get("position_id"),
            "protocol": position.get("protocol"),
            "type": "lending",
            "side": side,
            "symbol": symbol,
            "valueUsd": round(value_usd, 4),
            "riskScore": round(score, 2),
            "riskLevel": self._level(score),
            "healthFactor": round(health_factor, 4) if health_factor != 999 else 999,
            "liquidationThreshold": liquidation_threshold,
            "liquidationBufferUsd": round(context["liquidation_buffer_usd"], 4),
            "priceMoveToLiquidationPct": round(price_move_to_liquidation, 4) if price_move_to_liquidation is not None else None,
            "forecastLiquidationRiskPct": round(forecast_risk_pct, 4),
            "priceTrend": price_stats,
            "signals": signals,
            "model": {
                "name": "price_trend_liquidation_buffer",
                "usesProtocolThreshold": liquidation_threshold > 0,
                "windowDays": self.HISTORY_DAYS,
            },
            "history": self._position_history(wallet, position.get("position_id")),
        }

    def _analyze_lp_position(self, wallet: str, position: dict) -> dict:
        assets = position.get("asset") or []
        token0 = assets[0] if len(assets) > 0 else position.get("symbol")
        token1 = assets[1] if len(assets) > 1 else None
        value_usd = float(position.get("value_usd") or 0)
        amount0 = float(position.get("amount0") or 0)
        amount1 = float(position.get("amount1") or 0)
        deposited0 = float(position.get("deposited_token0") or 0)
        deposited1 = float(position.get("deposited_token1") or 0)
        withdrawn0 = float(position.get("withdrawn_token0") or 0)
        withdrawn1 = float(position.get("withdrawn_token1") or 0)
        price0 = self.pricing.get_price_safe(token0, 0.0)
        price1 = self.pricing.get_price_safe(token1, 0.0) if token1 else 0.0
        token_stats = self._price_stats([token for token in [token0, token1] if token])
        range_risk = self._lp_range_risk(position, price0, price1, token_stats)

        hold_value_usd = max(deposited0 - withdrawn0, 0) * price0 + max(deposited1 - withdrawn1, 0) * price1
        current_value_usd = value_usd or (amount0 * price0 + amount1 * price1)
        collected_fee_usd = float(position.get("collected_fee_usd") or 0)
        impermanent_loss_usd = current_value_usd + collected_fee_usd - hold_value_usd if hold_value_usd > 0 else 0.0
        impermanent_loss_pct = impermanent_loss_usd / hold_value_usd * 100 if hold_value_usd > 0 else 0.0
        forecast_il_pct = self._forecast_lp_il_pct(token_stats, token0, token1)
        forecast_il_usd = hold_value_usd * forecast_il_pct / 100 if hold_value_usd > 0 else 0.0

        signals = []
        score = 14.0
        if not range_risk["inRange"]:
            score += 40
            signals.append("LP is out of range and not earning fees")
        elif range_risk["distanceToRangeEdgePct"] is not None and range_risk["distanceToRangeEdgePct"] < 8:
            score += 22
            signals.append("LP price is close to range boundary")

        if range_risk.get("forecastOutOfRange"):
            score += 26
            signals.append("7 day forecast projects the LP can move out of range")

        if impermanent_loss_pct < -5:
            score += min(abs(impermanent_loss_pct) * 1.5, 25)
            signals.append("Estimated impermanent loss is material")
        if forecast_il_pct < -5:
            score += min(abs(forecast_il_pct), 18)
            signals.append("Projected price divergence can increase impermanent loss")

        max_volatility = max((item["volatility_30d_pct"] for item in token_stats.values()), default=0.0)
        if max_volatility > 8:
            score += 12
            signals.append("Pair has elevated token volatility")

        score = self._clamp(score, 0, 100)

        return {
            "positionId": position.get("position_id"),
            "protocol": position.get("protocol"),
            "type": "lp",
            "symbol": "/".join([token for token in [token0, token1] if token]),
            "token0": token0,
            "token1": token1,
            "valueUsd": round(current_value_usd, 4),
            "riskScore": round(score, 2),
            "riskLevel": self._level(score),
            "impermanentLossUsd": round(impermanent_loss_usd, 4),
            "impermanentLossPct": round(impermanent_loss_pct, 4),
            "forecastImpermanentLossUsd": round(forecast_il_usd, 4),
            "forecastImpermanentLossPct": round(forecast_il_pct, 4),
            "holdValueUsd": round(hold_value_usd, 4),
            "collectedFeeUsd": round(collected_fee_usd, 4),
            "range": range_risk,
            "priceTrend": token_stats,
            "signals": signals,
            "model": {
                "name": "lp_range_il_forecast",
                "windowDays": self.HISTORY_DAYS,
            },
            "history": self._position_history(wallet, position.get("position_id")),
        }

    def _lp_range_risk(self, position: dict, price0: float, price1: float, token_stats: dict[str, dict]) -> dict:
        tick_lower = position.get("tick_lower")
        tick_upper = position.get("tick_upper")
        if tick_lower is None or tick_upper is None or price0 <= 0 or price1 <= 0:
            return {
                "inRange": None,
                "currentTick": None,
                "tickLower": tick_lower,
                "tickUpper": tick_upper,
                "distanceToRangeEdgePct": None,
                "forecastTick7d": None,
                "forecastOutOfRange": None,
            }

        token0_price = float(position.get("token0_price") or 0)
        current_ratio = token0_price if token0_price > 0 else price1 / price0
        current_tick = math.log(current_ratio) / math.log(1.0001)
        lower = float(tick_lower)
        upper = float(tick_upper)
        in_range = lower <= current_tick <= upper
        width = max(upper - lower, 1.0)
        distance_ticks = min(abs(current_tick - lower), abs(upper - current_tick)) if in_range else 0.0
        distance_pct = distance_ticks / width * 100
        assets = position.get("asset") or []
        token0 = assets[0] if len(assets) > 0 else None
        token1 = assets[1] if len(assets) > 1 else None
        token0_forecast = token_stats.get(token0, {}).get("forecast_7d_pct", 0.0)
        token1_forecast = token_stats.get(token1, {}).get("forecast_7d_pct", 0.0)
        ratio_change = max(-0.95, (token1_forecast - token0_forecast) / 100)
        forecast_ratio = current_ratio * (1 + ratio_change)
        forecast_tick = math.log(forecast_ratio) / math.log(1.0001) if forecast_ratio > 0 else current_tick
        forecast_out_of_range = forecast_tick < lower or forecast_tick > upper

        return {
            "inRange": in_range,
            "currentTick": round(current_tick, 2),
            "tickLower": int(lower),
            "tickUpper": int(upper),
            "rangeWidthTicks": int(width),
            "distanceToRangeEdgePct": round(distance_pct, 4),
            "forecastTick7d": round(forecast_tick, 2),
            "forecastOutOfRange": forecast_out_of_range,
        }

    def _price_stats(self, symbols: list[str | None]) -> dict[str, dict]:
        now = int(datetime.now(timezone.utc).timestamp())
        from_ts = now - self.HISTORY_DAYS * 86400
        token_map = {}

        for symbol in symbols:
            if not symbol:
                continue
            try:
                token = self.pricing.get_token_info(symbol)
            except Exception:
                continue
            coingecko_id = token.get("coingeckoId")
            if coingecko_id:
                token_map[symbol] = coingecko_id

        histories = self.pricing.get_histories(list(token_map.values()), from_ts) if token_map else {}
        result = {}
        for symbol, coingecko_id in token_map.items():
            rows = histories.get(coingecko_id, [])
            result[symbol] = self._build_price_stats(symbol, rows)

        return result

    def _build_price_stats(self, symbol: str, rows: list[dict]) -> dict:
        if not rows:
            return self._empty_price_stats(symbol)

        prices = [float(row.get("price") or 0) for row in rows if float(row.get("price") or 0) > 0]
        if not prices:
            return self._empty_price_stats(symbol)

        current = prices[-1]
        first = prices[0]
        seven_day_index = max(len(prices) - 8, 0)
        seven_day_price = prices[seven_day_index]
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1] * 100
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]
        volatility = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        max_price = max(prices)
        max_drawdown = (current - max_price) / max_price * 100 if max_price > 0 else 0.0
        forecast_1d_pct, forecast_7d_pct, confidence = self._forecast_price_pct(prices)
        trend = "FLAT"
        if forecast_7d_pct > max(volatility, 1.5):
            trend = "UP"
        elif forecast_7d_pct < -max(volatility, 1.5):
            trend = "DOWN"

        return {
            "symbol": symbol,
            "currentPrice": round(current, 8),
            "change_7d_pct": round((current - seven_day_price) / seven_day_price * 100, 4) if seven_day_price > 0 else 0.0,
            "change_30d_pct": round((current - first) / first * 100, 4) if first > 0 else 0.0,
            "volatility_30d_pct": round(volatility, 4),
            "maxDrawdown_30d_pct": round(max_drawdown, 4),
            "forecast_1d_pct": round(forecast_1d_pct, 4),
            "forecast_7d_pct": round(forecast_7d_pct, 4),
            "trend": trend,
            "confidence": round(confidence, 4),
            "sampleSize": len(prices),
        }

    def _empty_price_stats(self, symbol: str | None) -> dict:
        return {
            "symbol": symbol,
            "currentPrice": self.pricing.get_price_safe(symbol, 0.0) if symbol else 0.0,
            "change_7d_pct": 0.0,
            "change_30d_pct": 0.0,
            "volatility_30d_pct": 0.0,
            "maxDrawdown_30d_pct": 0.0,
            "forecast_1d_pct": 0.0,
            "forecast_7d_pct": 0.0,
            "trend": "UNKNOWN",
            "confidence": 0.0,
            "sampleSize": 0,
        }

    def _forecast_price_pct(self, prices: list[float]) -> tuple[float, float, float]:
        if len(prices) < 3 or prices[-1] <= 0:
            return 0.0, 0.0, 0.0

        y = [math.log(price) for price in prices if price > 0]
        n = len(y)
        x_mean = (n - 1) / 2
        y_mean = sum(y) / n
        denom = sum((i - x_mean) ** 2 for i in range(n))
        if denom == 0:
            return 0.0, 0.0, 0.0

        slope = sum((i - x_mean) * (y[i] - y_mean) for i in range(n)) / denom
        residuals = [y[i] - (y_mean + slope * (i - x_mean)) for i in range(n)]
        residual_std = statistics.pstdev(residuals) if len(residuals) > 1 else 0.0
        forecast_1d = (math.exp(slope) - 1) * 100
        forecast_7d = (math.exp(slope * 7) - 1) * 100
        confidence = 1 / (1 + residual_std * 10)
        return forecast_1d, forecast_7d, confidence

    def _liquidation_probability(self, side: str, move_to_liquidation_pct: float | None, price_stats: dict) -> float:
        if move_to_liquidation_pct is None or move_to_liquidation_pct <= 0:
            return 100.0 if move_to_liquidation_pct == 0 else 0.0

        forecast = float(price_stats.get("forecast_7d_pct") or 0)
        volatility = max(float(price_stats.get("volatility_30d_pct") or 0), 0.01) * math.sqrt(7)
        if side in ("LENDER", "COLLATERAL"):
            threshold = -move_to_liquidation_pct
            z = (threshold - forecast) / volatility
            return self._normal_cdf(z) * 100
        if side == "BORROWER":
            threshold = move_to_liquidation_pct
            z = (threshold - forecast) / volatility
            return (1 - self._normal_cdf(z)) * 100

        return 0.0

    def _forecast_lp_il_pct(self, token_stats: dict[str, dict], token0: str | None, token1: str | None) -> float:
        if not token0 or not token1:
            return 0.0
        f0 = float(token_stats.get(token0, {}).get("forecast_7d_pct") or 0) / 100
        f1 = float(token_stats.get(token1, {}).get("forecast_7d_pct") or 0) / 100
        if 1 + f0 <= 0 or 1 + f1 <= 0:
            return 0.0
        relative_price_change = (1 + f0) / (1 + f1)
        if relative_price_change <= 0:
            return 0.0
        il = (2 * math.sqrt(relative_price_change) / (1 + relative_price_change) - 1) * 100
        return il

    def _normal_cdf(self, value: float) -> float:
        return 0.5 * (1 + math.erf(value / math.sqrt(2)))

    def _position_history(self, wallet: str, position_id: str | None) -> list[dict]:
        if not position_id:
            return []

        rows = self.position_snapshot_repository.get_wallet_position_history(wallet, position_id, limit=30)
        return [
            {
                "timestamp": row.get("timestamp"),
                "valueUsd": round(float(row.get("value_usd") or 0), 4),
                "pnlUsd": round(float(row.get("pnl_usd") or 0), 4),
            }
            for row in rows
        ]

    def _aggregate(self, risks: list[dict], latest_portfolio: dict) -> dict:
        total_value = sum(abs(float(item.get("valueUsd") or 0)) for item in risks)
        weighted_score = 0.0
        high_value = 0.0

        for item in risks:
            value = abs(float(item.get("valueUsd") or 0))
            score = float(item.get("riskScore") or 0)
            weighted_score += score * value
            if item.get("riskLevel") in ("HIGH", "CRITICAL"):
                high_value += value

        score = weighted_score / total_value if total_value > 0 else 0.0

        return {
            "netWorthUsd": round(float(latest_portfolio.get("net_worth_usd") or 0), 4),
            "totalRiskValueUsd": round(total_value, 4),
            "highRiskValueUsd": round(high_value, 4),
            "highRiskRatio": round(high_value / total_value, 4) if total_value > 0 else 0.0,
            "riskScore": round(score, 2),
            "riskLevel": self._level(score),
            "positionCount": len(risks),
        }

    def _persist(self, result: dict):
        timestamp = result["timestamp"]
        wallet = result["wallet"]
        portfolio = result["portfolio"]
        rows = [
            {
                "wallet": wallet,
                "timestamp": timestamp,
                "scope": "portfolio",
                "position_id": None,
                "risk_score": portfolio["riskScore"],
                "risk_level": portfolio["riskLevel"],
                "payload": portfolio,
                "created_at": datetime.now(timezone.utc),
            }
        ]

        for position in result["positions"]:
            rows.append(
                {
                    "wallet": wallet,
                    "timestamp": timestamp,
                    "scope": "position",
                    "position_id": position.get("positionId"),
                    "protocol": position.get("protocol"),
                    "position_type": position.get("type"),
                    "symbol": position.get("symbol"),
                    "value_usd": position.get("valueUsd"),
                    "risk_score": position.get("riskScore"),
                    "risk_level": position.get("riskLevel"),
                    "payload": position,
                    "input_snapshot": {
                        "price_trend": position.get("priceTrend"),
                        "range": position.get("range"),
                        "model": position.get("model"),
                        "liquidation_threshold": position.get("liquidationThreshold"),
                        "price_move_to_liquidation_pct": position.get("priceMoveToLiquidationPct"),
                        "forecast_liquidation_risk_pct": position.get("forecastLiquidationRiskPct"),
                        "forecast_il_pct": position.get("forecastImpermanentLossPct"),
                    },
                    "created_at": datetime.now(timezone.utc),
                }
            )

        self.risk_snapshot_repository.bulk_insert(rows)

    def _level(self, score: float) -> str:
        if score >= 85:
            return "CRITICAL"
        if score >= 65:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min(value, max_value), min_value)
