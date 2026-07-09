import math
import statistics
from datetime import datetime, timezone

from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_risk_snapshot_repository import \
    PositionRiskSnapshotRepository
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
        positions = self.position_snapshot_repository.get_latest_wallet_positions(
            wallet
            )
        lending_context = self._build_lending_context(positions)

        position_risks = []
        for position in positions:
            if position.get("type") == "amm":
                position_risks.append(self._analyze_lp_position(wallet, position))
            else:
                position_risks.append(
                    self._analyze_lending_position(wallet, position, lending_context)
                    )

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
        rows = self.risk_snapshot_repository.get_portfolio_risk_history(
            wallet.lower(),
            limit=limit
            )
        return [{
            "timestamp": row.get("timestamp"),
            "riskScore": row.get("risk_score"),
            "riskLevel": row.get("risk_level"), **(row.get("payload") or {}),
        } for row in rows]

    def _build_lending_context(self, positions: list[dict]) -> dict:
        collateral_positions = [p for p in positions if
            p.get("side") in ("LENDER", "COLLATERAL") and p.get("type") != "amm"]
        borrow_positions = [p for p in positions if
            p.get("side") == "BORROWER" and p.get("type") != "amm"]
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

        health_factor = weighted_collateral / debt_usd if debt_usd > 0 and weighted_collateral > 0 else (
            999.0 if debt_usd <= 0 else None)
        liquidation_buffer = weighted_collateral - debt_usd

        return {
            "collateral_usd": collateral_usd,
            "debt_usd": debt_usd,
            "weighted_collateral_usd": weighted_collateral,
            "health_factor": health_factor,
            "liquidation_buffer_usd": liquidation_buffer,
            "missing_threshold_positions": missing_threshold_positions,
        }

    def _analyze_lending_position(self,
                                  wallet: str,
                                  position: dict,
                                  context: dict) -> dict:
        symbol = position.get("symbol")
        side = position.get("side")
        value_usd = float(position.get("value_usd") or 0)
        price_stats = self._price_stats([symbol]).get(
            symbol,
            self._empty_price_stats(symbol)
            )
        health_factor = context["health_factor"]
        liquidation_threshold = float(position.get("liquidation_threshold") or 0)
        weighted_collateral = context["weighted_collateral_usd"]
        debt_usd = context["debt_usd"]

        price_move_to_liquidation = None
        if side in ("LENDER", "COLLATERAL") and value_usd > 0 and debt_usd > 0:
            collateral_contribution = value_usd * liquidation_threshold
            if collateral_contribution > 0:
                price_move_to_liquidation = (
                                                    weighted_collateral - debt_usd) / collateral_contribution * 100
        elif side == "BORROWER" and value_usd > 0 and debt_usd > 0:
            if weighted_collateral > debt_usd:
                price_move_to_liquidation = (weighted_collateral / debt_usd - 1) * (
                        debt_usd / value_usd) * 100
            else:
                price_move_to_liquidation = 0.0

        forecast_risk_pct = self._liquidation_probability(
            side,
            price_move_to_liquidation,
            price_stats
            )
        signals = []
        score = 12.0

        if debt_usd > 0 and liquidation_threshold <= 0 and side in ("LENDER",
                                                                    "COLLATERAL"):
            score += 22
            signals.append(
                "Missing protocol liquidation threshold for this collateral; risk model confidence is reduced"
                )

        if health_factor is not None and health_factor != 999:
            if health_factor <= 1:
                score += 65
                signals.append(
                    "Current weighted collateral is below debt; liquidation can happen now"
                    )
            elif price_move_to_liquidation is not None:
                buffer_component = max(
                    0.0,
                    min(45.0, 45.0 * (1 - min(price_move_to_liquidation, 50.0) / 50.0))
                    )
                score += buffer_component
                if price_move_to_liquidation < abs(
                    price_stats.get("forecast_7d_pct") or 0
                    ) + price_stats.get("volatility_30d_pct", 0):
                    signals.append(
                        "7 day forecast plus volatility can consume liquidation buffer"
                        )

        if side in ("LENDER", "COLLATERAL"):
            if price_stats["trend"] == "DOWN":
                score += 12
                signals.append(
                    "Collateral token trend is down based on recent price history"
                    )
        elif side == "BORROWER":
            if price_stats["trend"] == "UP":
                score += 12
                signals.append("Borrowed token trend is up, increasing debt value risk")

        if forecast_risk_pct > 35:
            score += min(25, forecast_risk_pct / 2)
            signals.append(
                "Forecast model shows elevated probability of touching liquidation conditions"
                )

        if price_stats["volatility_30d_pct"] > max(
            abs(price_stats["forecast_7d_pct"]),
            1
            ) * 1.5:
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
            "priceMoveToLiquidationPct": round(
                price_move_to_liquidation,
                4
                ) if price_move_to_liquidation is not None else None,
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
        v3_metrics = self._lp_v3_metrics(position, price0, price1)

        hold0 = max(deposited0 - withdrawn0, 0)
        hold1 = max(deposited1 - withdrawn1, 0)
        hold_value_usd = hold0 * price0 + hold1 * price1
        current_value_usd = (float(v3_metrics.get("valueUsd") or 0) if v3_metrics.get(
            "formulaApplied"
            ) else value_usd or (amount0 * price0 + amount1 * price1))
        collected_fee_usd = float(position.get("collected_fee_usd") or 0)
        impermanent_loss_usd = current_value_usd + collected_fee_usd - hold_value_usd if hold_value_usd > 0 else 0.0
        impermanent_loss_pct = impermanent_loss_usd / hold_value_usd * 100 if hold_value_usd > 0 else 0.0
        forecast_il_usd, forecast_il_pct, forecast_context = self._forecast_lp_v3_il(
            position=position,
            token_stats=token_stats,
            token0=token0,
            token1=token1,
            price0=price0,
            price1=price1,
            hold0=hold0,
            hold1=hold1,
            collected_fee_usd=collected_fee_usd,
            v3_metrics=v3_metrics, )

        signals = []
        score = 14.0
        if range_risk["inRange"] is False:
            score += 40
            signals.append("LP is out of range and not earning fees")
        elif range_risk["inRange"] is True and range_risk.get(
            "distanceToRangeEdgeAtr"
            ) is not None and range_risk["distanceToRangeEdgeAtr"] < 1.25:
            score += 24
            signals.append("LP price is within roughly one ATR of a range boundary")
        elif range_risk["inRange"] is True and range_risk[
            "distanceToRangeEdgePct"] is not None and range_risk[
            "distanceToRangeEdgePct"] < 8:
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

        max_volatility = max(
            (item["volatility_30d_pct"] for item in token_stats.values()),
            default=0.0
            )
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
            "v3": v3_metrics,
            "priceTrend": token_stats,
            "signals": signals,
            "model": {
                "name": "uniswap_v3_concentrated_liquidity_risk",
                "windowDays": self.HISTORY_DAYS,
                "impermanentLossModel": forecast_context.get("model"),
                "forecast": forecast_context,
            },
            "history": self._position_history(wallet, position.get("position_id")),
        }

    def _lp_range_risk(self,
                       position: dict,
                       price0: float,
                       price1: float,
                       token_stats: dict[str, dict]) -> dict:
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

        current_ratio = self._lp_current_ratio(position, price0, price1)
        if current_ratio <= 0:
            return {
                "inRange": None,
                "currentTick": None,
                "tickLower": tick_lower,
                "tickUpper": tick_upper,
                "distanceToRangeEdgePct": None,
                "forecastTick7d": None,
                "forecastOutOfRange": None,
            }

        current_tick = self._tick_from_price_ratio(current_ratio, position)
        lower = float(tick_lower)
        upper = float(tick_upper)
        lower_ratio = self._tick_to_price(lower, position)
        upper_ratio = self._tick_to_price(upper, position)
        in_range = lower_ratio <= current_ratio <= upper_ratio
        width = max(upper - lower, 1.0)
        distance_ticks = min(
            abs(current_tick - lower),
            abs(upper - current_tick)
            ) if in_range else 0.0
        distance_pct = distance_ticks / width * 100
        assets = position.get("asset") or []
        token0 = assets[0] if len(assets) > 0 else None
        token1 = assets[1] if len(assets) > 1 else None
        token0_forecast = token_stats.get(token0, {}).get("forecast_7d_pct", 0.0)
        token1_forecast = token_stats.get(token1, {}).get("forecast_7d_pct", 0.0)
        ratio_change = self._relative_ratio_change(token0_forecast, token1_forecast)
        forecast_ratio = current_ratio * ratio_change
        forecast_tick = self._tick_from_price_ratio(
            forecast_ratio,
            position
            ) if forecast_ratio > 0 else current_tick
        ratio_atr_pct = self._pair_atr_pct(token_stats, token0, token1)
        ratio_atr_7d = ratio_atr_pct / 100 * math.sqrt(7)
        projected_low_ratio = forecast_ratio * max(0.01, 1 - ratio_atr_7d)
        projected_high_ratio = forecast_ratio * (1 + ratio_atr_7d)
        projected_low_tick = self._tick_from_price_ratio(
            projected_low_ratio,
            position
            ) if projected_low_ratio > 0 else forecast_tick
        projected_high_tick = self._tick_from_price_ratio(
            projected_high_ratio,
            position
            ) if projected_high_ratio > 0 else forecast_tick
        forecast_out_of_range = (
            forecast_tick < lower or forecast_tick > upper or projected_low_tick < lower or projected_high_tick > upper)
        if in_range:
            edge_down_pct = (
                                    current_ratio / lower_ratio - 1) * 100 if lower_ratio > 0 else None
            edge_up_pct = (
                                  upper_ratio / current_ratio - 1) * 100 if current_ratio > 0 else None
            edge_distances = [value for value in [edge_down_pct, edge_up_pct] if
                              value is not None and value >= 0]
            distance_to_edge_atr = min(
                edge_distances
                ) / ratio_atr_pct if edge_distances and ratio_atr_pct > 0 else None
        else:
            edge_down_pct = None
            edge_up_pct = None
            distance_to_edge_atr = 0.0

        return {
            "inRange": in_range,
            "currentTick": round(current_tick, 2),
            "tickLower": int(lower),
            "tickUpper": int(upper),
            "rangeWidthTicks": int(width),
            "priceLower": round(lower_ratio, 12),
            "priceUpper": round(upper_ratio, 12),
            "currentPriceRatio": round(current_ratio, 12),
            "distanceToRangeEdgePct": round(distance_pct, 4),
            "distanceToLowerEdgePct": round(
                edge_down_pct,
                4
                ) if edge_down_pct is not None else None,
            "distanceToUpperEdgePct": round(
                edge_up_pct,
                4
                ) if edge_up_pct is not None else None,
            "distanceToRangeEdgeAtr": round(
                distance_to_edge_atr,
                4
                ) if distance_to_edge_atr is not None else None,
            "forecastTick7d": round(forecast_tick, 2),
            "projectedLowerTick7d": round(projected_low_tick, 2),
            "projectedUpperTick7d": round(projected_high_tick, 2),
            "forecastOutOfRange": forecast_out_of_range,
            "pairAtr7dPct": round(ratio_atr_pct * math.sqrt(7), 4),
        }

    def _lp_v3_metrics(self, position: dict, price0: float, price1: float) -> dict:
        tick_lower = position.get("tick_lower")
        tick_upper = position.get("tick_upper")
        amount0 = float(position.get("amount0") or 0)
        amount1 = float(position.get("amount1") or 0)
        current_ratio = self._lp_current_ratio(position, price0, price1)
        if tick_lower is None or tick_upper is None or current_ratio <= 0 or price0 <= 0 or price1 <= 0:
            return {
                "formulaApplied": False,
                "reason": "missing_tick_or_price",
                "amount0": round(amount0, 8),
                "amount1": round(amount1, 8),
                "valueUsd": round(amount0 * price0 + amount1 * price1, 4),
                "rawLiquidity": position.get("liquidity"),
            }

        lower = float(tick_lower)
        upper = float(tick_upper)
        sqrt_price = math.sqrt(current_ratio)
        lower_ratio = self._tick_to_price(lower, position)
        upper_ratio = self._tick_to_price(upper, position)
        sqrt_lower = math.sqrt(lower_ratio)
        sqrt_upper = math.sqrt(upper_ratio)
        if sqrt_lower <= 0 or sqrt_upper <= sqrt_lower:
            return {
                "formulaApplied": False,
                "reason": "invalid_tick_range",
                "amount0": round(amount0, 8),
                "amount1": round(amount1, 8),
                "valueUsd": round(amount0 * price0 + amount1 * price1, 4),
                "rawLiquidity": position.get("liquidity"),
            }

        effective_liquidity = self._estimate_effective_liquidity(
            amount0=amount0,
            amount1=amount1,
            sqrt_price=sqrt_price,
            sqrt_lower=sqrt_lower,
            sqrt_upper=sqrt_upper, )
        if effective_liquidity <= 0:
            return {
                "formulaApplied": False,
                "reason": "insufficient_amounts",
                "currentPriceRatio": round(current_ratio, 12),
                "priceLower": round(lower_ratio, 12),
                "priceUpper": round(upper_ratio, 12),
                "amount0": round(amount0, 8),
                "amount1": round(amount1, 8),
                "valueUsd": round(amount0 * price0 + amount1 * price1, 4),
                "rawLiquidity": position.get("liquidity"),
            }

        v3_amount0, v3_amount1 = self._v3_amounts_from_liquidity(
            liquidity=effective_liquidity,
            sqrt_price=sqrt_price,
            sqrt_lower=sqrt_lower,
            sqrt_upper=sqrt_upper, )
        value_usd = v3_amount0 * price0 + v3_amount1 * price1
        current_tick = self._tick_from_price_ratio(current_ratio, position)

        return {
            "formulaApplied": True,
            "currentPriceRatio": round(current_ratio, 12),
            "priceLower": round(lower_ratio, 12),
            "priceUpper": round(upper_ratio, 12),
            "sqrtPrice": round(sqrt_price, 12),
            "currentTick": round(current_tick, 2),
            "tickLower": int(lower),
            "tickUpper": int(upper),
            "effectiveLiquidity": round(effective_liquidity, 12),
            "rawLiquidity": position.get("liquidity"),
            "token0Decimals": position.get("token0_decimals"),
            "token1Decimals": position.get("token1_decimals"),
            "amount0": round(v3_amount0, 8),
            "amount1": round(v3_amount1, 8),
            "snapshotAmount0": round(amount0, 8),
            "snapshotAmount1": round(amount1, 8),
            "valueUsd": round(value_usd, 4),
            "liquidityUnit": "normalized_token_amounts",
            "formula": "x=L(1/sqrt(P)-1/sqrt(P_U)); y=L(sqrt(P)-sqrt(P_L))",
        }

    # --- ĐOẠN BỔ SUNG HOÀN THIỆN TOÀN BỘ LOGIC BỊ THIẾU ---

    def _forecast_lp_v3_il(self,
        position: dict,
        token_stats: dict[str, dict],
        token0: str | None,
        token1: str | None,
        price0: float,
        price1: float,
        hold0: float,
        hold1: float,
        collected_fee_usd: float,
        v3_metrics: dict, ) -> tuple[float, float, dict]:
        hold_value_usd = hold0 * price0 + hold1 * price1
        if hold_value_usd <= 0 or not token0 or not token1:
            return 0.0, 0.0, {"model": "none", "reason": "invalid_hold_value_or_tokens"}

        t0_forecast = token_stats.get(token0, {}).get("forecast_7d_pct", 0.0)
        t1_forecast = token_stats.get(token1, {}).get("forecast_7d_pct", 0.0)

        price0_f = price0 * (1 + t0_forecast / 100)
        price1_f = price1 * (1 + t1_forecast / 100)
        hold_value_f = hold0 * price0_f + hold1 * price1_f

        if not v3_metrics.get("formulaApplied"):
            return 0.0, 0.0, {
                "model": "hold_fallback",
                "reason": "v3_metrics_not_applied"
            }

        liquidity = v3_metrics["effectiveLiquidity"]
        sqrt_lower = math.sqrt(v3_metrics["priceLower"])
        sqrt_upper = math.sqrt(v3_metrics["priceUpper"])

        ratio_f = price0_f / price1_f if price1_f > 0 else v3_metrics[
            "currentPriceRatio"]
        sqrt_price_f = math.sqrt(ratio_f)

        v3_amt0_f, v3_amt1_f = self._v3_amounts_from_liquidity(
            liquidity,
            sqrt_price_f,
            sqrt_lower,
            sqrt_upper
            )
        v3_value_f = v3_amt0_f * price0_f + v3_amt1_f * price1_f + collected_fee_usd

        forecast_il_usd = v3_value_f - hold_value_f
        forecast_il_pct = (
                forecast_il_usd / hold_value_f * 100) if hold_value_f > 0 else 0.0

        context = {
            "model": "uniswap_v3_analytical_divergence",
            "projectedPrice0": round(price0_f, 4),
            "projectedPrice1": round(price1_f, 4),
            "projectedHoldValueUsd": round(hold_value_f, 4),
            "projectedLpValueUsd": round(v3_value_f, 4),
        }
        return forecast_il_usd, forecast_il_pct, context

    def _lp_current_ratio(self, position: dict, price0: float, price1: float) -> float:
        if price1 <= 0 or price0 <= 0:
            return 0.0
        dec0 = int(position.get("token0_decimals") or 18)
        dec1 = int(position.get("token1_decimals") or 18)
        # Tỷ giá ratio = Token0 / Token1 trong smart contract cần normalize decimals
        raw_ratio = price0 / price1
        return raw_ratio * (10 ** (dec0 - dec1))

    def _tick_to_price(self, tick: float, position: dict) -> float:
        return 1.0001 ** tick

    def _tick_from_price_ratio(self, ratio: float, position: dict) -> float:
        if ratio <= 0:
            return 0.0
        return math.log(ratio) / math.log(1.0001)

    def _estimate_effective_liquidity(self,
                                      amount0: float,
                                      amount1: float,
                                      sqrt_price: float,
                                      sqrt_lower: float,
                                      sqrt_upper: float) -> float:
        if sqrt_price <= sqrt_lower:
            return amount0 * (sqrt_lower * sqrt_upper) / (sqrt_upper - sqrt_lower) if (
                                                                                              sqrt_upper - sqrt_lower) > 0 else 0.0
        elif sqrt_price < sqrt_upper:
            l0 = amount0 * (sqrt_price * sqrt_upper) / (sqrt_upper - sqrt_price) if (
                                                                                            sqrt_upper - sqrt_price) > 0 else float(
                'inf'
                )
            l1 = amount1 / (sqrt_price - sqrt_lower) if (
                                                                sqrt_price - sqrt_lower) > 0 else float(
                'inf'
                )
            return min(l0, l1)
        else:
            return amount1 / (sqrt_upper - sqrt_lower) if (
                                                                  sqrt_upper - sqrt_lower) > 0 else 0.0

    def _v3_amounts_from_liquidity(self,
                                   liquidity: float,
                                   sqrt_price: float,
                                   sqrt_lower: float,
                                   sqrt_upper: float) -> tuple[float, float]:
        if sqrt_price <= sqrt_lower:
            amount0 = liquidity * (sqrt_upper - sqrt_lower) / (sqrt_lower * sqrt_upper)
            return amount0, 0.0
        elif sqrt_price < sqrt_upper:
            amount0 = liquidity * (sqrt_upper - sqrt_price) / (sqrt_price * sqrt_upper)
            amount1 = liquidity * (sqrt_price - sqrt_lower)
            return amount0, amount1
        else:
            amount1 = liquidity * (sqrt_upper - sqrt_lower)
            return 0.0, amount1

    def _price_stats(self, symbols: list[str]) -> dict[str, dict]:
        stats = {}
        from_ts = int(datetime.now(timezone.utc).timestamp()) - self.HISTORY_DAYS * 86400

        for sym in symbols:
            if not sym:
                continue
            try:
                normalized = self.pricing.normalize_symbol(sym)
                token = self.pricing.get_token_info(normalized)
                coingecko_id = token.get("coingeckoId")
                if not coingecko_id:
                    stats[sym] = self._empty_price_stats(sym)
                    continue

                rows = self.pricing.get_histories([coingecko_id], from_ts).get(coingecko_id, [])
                stat = self._build_price_stats(normalized, rows[-self.HISTORY_DAYS:])
                stats[sym] = stat
                stats[normalized] = stat
            except Exception:
                stats[sym] = self._empty_price_stats(sym)
        return stats

    def _empty_price_stats(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "model": "ema_weighted_log_regression",
            "currentPrice": 0.0,
            "change_7d_pct": 0.0,
            "change_30d_pct": 0.0,
            "maxDrawdown_30d_pct": 0.0,
            "trend": "UNKNOWN",
            "forecast_1d_pct": 0.0,
            "forecast_7d_pct": 0.0,
            "volatility_30d_pct": 0.0,
            "atr_14d_pct": 0.0,
            "noise_band_7d_pct": 0.0,
            "confidence": 0.0,
            "sampleSize": 0
        }

    def _build_price_stats(self, symbol: str, rows: list[dict]) -> dict:
        clean_rows = [
            row for row in rows
            if float(row.get("price") or 0) > 0
        ]
        if len(clean_rows) < 3:
            return self._empty_price_stats(symbol)

        if clean_rows and clean_rows[0].get("timestamp") is not None:
            clean_rows = sorted(clean_rows, key=lambda item: int(item.get("timestamp") or 0))
        clean_rows = clean_rows[-self.HISTORY_DAYS:]
        prices = [float(r["price"]) for r in clean_rows]
        sample_size = len(prices)
        current_price = prices[-1]
        first_price = prices[0]
        seven_day_index = max(sample_size - 8, 0)
        seven_day_price = prices[seven_day_index]
        max_price = max(prices)
        change_7d_pct = (
            (current_price - seven_day_price) / seven_day_price * 100
            if seven_day_price > 0
            else 0.0
        )
        change_30d_pct = (
            (current_price - first_price) / first_price * 100
            if first_price > 0
            else 0.0
        )
        max_drawdown_pct = (
            (current_price - max_price) / max_price * 100
            if max_price > 0
            else 0.0
        )

        ema_prices = self._ema_series(prices, span=min(10, sample_size))
        y_values = [math.log(price) for price in ema_prices if price > 0]
        x_values = list(range(len(y_values)))
        weights = [index + 1 for index in x_values]

        slope, intercept = self._weighted_linear_regression(x_values, y_values, weights)
        forecast_1d = (math.exp(slope) - 1) * 100
        regression_7d = (math.exp(slope * 7) - 1) * 100
        ema_momentum_7d = self._ema_momentum_7d_pct(ema_prices)
        forecast_7d = 0.7 * regression_7d + 0.3 * ema_momentum_7d

        log_returns = [
            math.log(prices[i] / prices[i - 1])
            for i in range(1, sample_size)
            if prices[i - 1] > 0 and prices[i] > 0
        ]
        volatility = statistics.pstdev(log_returns) * 100 if len(log_returns) > 1 else 0.0
        atr_14d_pct = self._atr_pct(prices[-15:])
        noise_band = max(atr_14d_pct * math.sqrt(7), volatility * math.sqrt(7), 1.5)

        residuals = [
            y - (intercept + slope * x)
            for x, y in zip(x_values, y_values)
        ]
        residual_std = statistics.pstdev(residuals) if len(residuals) > 1 else 0.0
        confidence = 1 / (1 + 12 * residual_std)

        if forecast_7d > noise_band:
            trend = "UP"
        elif forecast_7d < -noise_band:
            trend = "DOWN"
        else:
            trend = "FLAT"

        return {
            "symbol": symbol,
            "model": "ema_weighted_log_regression",
            "currentPrice": round(current_price, 8),
            "change_7d_pct": round(change_7d_pct, 4),
            "change_30d_pct": round(change_30d_pct, 4),
            "maxDrawdown_30d_pct": round(max_drawdown_pct, 4),
            "trend": trend,
            "forecast_1d_pct": round(forecast_1d, 4),
            "forecast_7d_pct": round(forecast_7d, 4),
            "volatility_30d_pct": round(volatility, 4),
            "atr_14d_pct": round(atr_14d_pct, 4),
            "noise_band_7d_pct": round(noise_band, 4),
            "confidence": round(confidence, 4),
            "sampleSize": sample_size
        }

    def _liquidation_probability(self,
                                 side: str,
                                 move_pct: float | None,
                                 stats: dict) -> float:
        if move_pct is None:
            return 0.0
        if move_pct <= 0:
            return 100.0
        forecast_7d = float(stats.get("forecast_7d_pct") or 0.0)
        volatility_7d = max(float(stats.get("volatility_30d_pct") or 0.0) * math.sqrt(7), 0.01)
        normalized_side = (side or "").upper()

        if normalized_side in ("LENDER", "COLLATERAL"):
            z_score = (-move_pct - forecast_7d) / volatility_7d
            probability = self._normal_cdf(z_score) * 100
        elif normalized_side == "BORROWER":
            z_score = (move_pct - forecast_7d) / volatility_7d
            probability = (1 - self._normal_cdf(z_score)) * 100
        else:
            probability = 0.0
        return self._clamp(probability, 0.0, 100.0)

    def _ema_series(self, prices: list[float], span: int) -> list[float]:
        if not prices:
            return []
        alpha = 2 / (max(span, 1) + 1)
        ema = [prices[0]]
        for price in prices[1:]:
            ema.append(alpha * price + (1 - alpha) * ema[-1])
        return ema

    def _weighted_linear_regression(
        self,
        x_values: list[float],
        y_values: list[float],
        weights: list[float],
    ) -> tuple[float, float]:
        total_weight = sum(weights)
        if total_weight <= 0 or len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0, y_values[0] if y_values else 0.0

        mean_x = sum(w * x for w, x in zip(weights, x_values)) / total_weight
        mean_y = sum(w * y for w, y in zip(weights, y_values)) / total_weight
        variance_x = sum(w * ((x - mean_x) ** 2) for w, x in zip(weights, x_values))
        if variance_x <= 0:
            return 0.0, mean_y

        covariance = sum(
            w * (x - mean_x) * (y - mean_y)
            for w, x, y in zip(weights, x_values, y_values)
        )
        slope = covariance / variance_x
        intercept = mean_y - slope * mean_x
        return slope, intercept

    def _ema_momentum_7d_pct(self, ema_prices: list[float]) -> float:
        if len(ema_prices) < 2:
            return 0.0
        lookback = min(7, len(ema_prices) - 1)
        previous = ema_prices[-1 - lookback]
        current = ema_prices[-1]
        return (current / previous - 1) * 100 if previous > 0 else 0.0

    def _atr_pct(self, prices: list[float]) -> float:
        if len(prices) < 2:
            return 0.0
        ranges = [
            abs(prices[i] - prices[i - 1]) / prices[i - 1] * 100
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]
        return sum(ranges) / len(ranges) if ranges else 0.0

    def _normal_cdf(self, value: float) -> float:
        return 0.5 * (1 + math.erf(value / math.sqrt(2)))

    def _relative_ratio_change(self, t0_pct: float, t1_pct: float) -> float:
        return (1 + t0_pct / 100) / (1 + t1_pct / 100)

    def _pair_atr_pct(self, token_stats: dict, t0: str | None, t1: str | None) -> float:
        v0 = token_stats.get(t0, {}).get("volatility_30d_pct", 0.0) if t0 else 0.0
        v1 = token_stats.get(t1, {}).get("volatility_30d_pct", 0.0) if t1 else 0.0
        return math.sqrt(v0 ** 2 + v1 ** 2)

    def _aggregate(self, position_risks: list[dict], portfolio: dict) -> dict:
        if not position_risks:
            return {
                "netWorthUsd": round(float(portfolio.get("net_worth_usd") or 0), 4),
                "totalRiskValueUsd": 0.0,
                "highRiskValueUsd": 0.0,
                "highRiskRatio": 0.0,
                "riskScore": 0.0,
                "riskLevel": "LOW",
                "positionCount": 0,
            }

        total_value = sum(abs(float(item.get("valueUsd") or 0)) for item in position_risks)
        if total_value > 0:
            risk_score = sum(
                float(item.get("riskScore") or 0) * abs(float(item.get("valueUsd") or 0))
                for item in position_risks
            ) / total_value
        else:
            risk_score = sum(float(item.get("riskScore") or 0) for item in position_risks) / len(position_risks)

        high_risk_value = sum(
            abs(float(item.get("valueUsd") or 0))
            for item in position_risks
            if item.get("riskLevel") in ("HIGH", "CRITICAL")
        )

        return {
            "netWorthUsd": round(float(portfolio.get("net_worth_usd") or 0), 4),
            "totalRiskValueUsd": round(total_value, 4),
            "highRiskValueUsd": round(high_risk_value, 4),
            "highRiskRatio": round(high_risk_value / total_value * 100, 4) if total_value > 0 else 0.0,
            "riskScore": round(risk_score, 2),
            "riskLevel": self._level(risk_score),
            "positionCount": len(position_risks),
        }

    def _level(self, score: float) -> str:
        if score >= 85:
            return "CRITICAL"
        if score >= 65:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    def _clamp(self, val: float, min_v: float, max_v: float) -> float:
        return max(min_v, min(max_v, val))

    def _position_history(self, wallet: str, pos_id: str | None) -> list:
        if not pos_id:
            return []
        rows = self.position_snapshot_repository.get_wallet_position_history(
            wallet,
            pos_id,
            limit=30,
        )
        return [
            {
                "timestamp": row.get("timestamp"),
                "valueUsd": round(float(row.get("value_usd") or 0), 4),
                "pnlUsd": round(float(row.get("pnl_usd") or 0), 4),
            }
            for row in rows
        ]

    def _persist(self, data: dict) -> None:
        wallet = data["wallet"]
        timestamp = data["timestamp"]
        portfolio = data.get("portfolio") or {}
        rows = [
            {
                "wallet": wallet,
                "timestamp": timestamp,
                "scope": "portfolio",
                "position_id": None,
                "risk_score": portfolio.get("riskScore", 0.0),
                "risk_level": portfolio.get("riskLevel", "LOW"),
                "payload": portfolio,
                "created_at": datetime.now(timezone.utc),
            }
        ]

        for position in data.get("positions") or []:
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
                    "risk_score": position.get("riskScore", 0.0),
                    "risk_level": position.get("riskLevel", "LOW"),
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
