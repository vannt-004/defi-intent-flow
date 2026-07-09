from datetime import datetime, timezone
from math import sqrt

from data_engine.services.prices.pricing_service import PricingService
from portfolio_engine.ai_agent.intent_extractor import NLPIntentExtractor
from shared.databases.mongo_client import MongoConnection
from shared.repositories.asset_snapshot_repository import AssetSnapshotRepository
from shared.repositories.cashflow_repository import CashflowRepository
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository
from shared.repositories.yield_repository import YieldRepository


class SimulationService:
    DEFAULT_GAS_USD = {
        "swap": 8.0,
        "lend": 6.0,
        "stake": 6.0,
        "borrow": 9.0,
        "add_liquidity": 14.0,
        "price_shock": 0.0,
    }

    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)
        self.portfolio_repository = PortfolioRepository(self.db)
        self.asset_repository = AssetSnapshotRepository(self.db)
        self.cashflow_repository = CashflowRepository(self.db)
        self.position_repository = PositionSnapshotRepository(self.db)
        self.yield_repository = YieldRepository(self.db)
        self.intent_extractor = NLPIntentExtractor()

    def simulate(self, wallet: str, payload: dict) -> dict:
        wallet = wallet.lower()
        scenario_type = payload.get("type") or payload.get("action") or "price_shock"
        latest = self.portfolio_repository.get_latest_snapshot(wallet) or {}
        assets = self.asset_repository.get_latest_wallet_assets(wallet)
        positions = self.position_repository.get_latest_wallet_positions(wallet)
        fee_model = self._fee_model(wallet)
        before = self._summary(latest, assets, positions)

        if scenario_type == "price_shock":
            result = self._simulate_price_shock(before, assets, positions, payload)
        elif scenario_type in ("lend", "stake"):
            result = self._simulate_lend(before, assets, payload, scenario_type, fee_model)
        elif scenario_type == "borrow":
            result = self._simulate_borrow(before, payload, fee_model)
        elif scenario_type == "swap":
            result = self._simulate_swap(before, assets, payload, fee_model)
        elif scenario_type == "loop_lending":
            result = self._simulate_loop_lending(before, assets, payload, fee_model)
        elif scenario_type in ("provide_liquidity", "lp"):
            result = self._simulate_provide_liquidity(before, assets, payload, fee_model)
        else:
            result = {
                "after": before,
                "changes": [],
                "warnings": [f"Unsupported simulation action: {scenario_type}"],
                "assumptions": [],
            }

        after = result["after"]
        return {
            "wallet": wallet,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "type": scenario_type,
            "before": before,
            "after": after,
            "delta": {
                "netWorthUsd": round(after["netWorthUsd"] - before["netWorthUsd"], 4),
                "tokenHoldUsd": round(after["tokenHoldUsd"] - before["tokenHoldUsd"], 4),
                "positionUsd": round(after["positionUsd"] - before["positionUsd"], 4),
                "borrowUsd": round(after["borrowUsd"] - before["borrowUsd"], 4),
            },
            "changes": result.get("changes", []),
            "warnings": result.get("warnings", []),
            "assumptions": result.get("assumptions", []),
            "strategy": result.get("strategy"),
            "feeModel": fee_model,
            "notice": "Simulation only. This is not investment advice and does not execute transactions.",
        }

    def parse_intent(self, text: str) -> dict:
        return self.intent_extractor.extract(text)

    def _simulate_price_shock(self, before: dict, assets: list[dict], positions: list[dict], payload: dict) -> dict:
        shocks = {k.upper(): float(v) for k, v in (payload.get("shocks") or {}).items()}
        after = dict(before)
        changes = []
        warnings = []
        token_delta = 0.0
        position_delta = 0.0
        borrow_delta = 0.0

        for asset in assets:
            symbol = str(asset.get("symbol") or "").upper()
            if symbol not in shocks:
                continue
            value = float(asset.get("value_usd") or 0)
            delta = value * shocks[symbol] / 100
            token_delta += delta
            changes.append({"label": f"{symbol} wallet value", "deltaUsd": round(delta, 4)})

        for position in positions:
            symbols = [str(x).upper() for x in (position.get("asset") or [position.get("symbol")]) if x]
            matched = [shocks[s] for s in symbols if s in shocks]
            if not matched:
                continue
            avg_shock = sum(matched) / len(matched)
            value = float(position.get("value_usd") or 0)
            delta = value * avg_shock / 100
            if position.get("side") == "BORROWER":
                borrow_delta += delta
            else:
                position_delta += delta
            changes.append({"label": f"{position.get('protocol')} {position.get('symbol')}", "deltaUsd": round(delta, 4)})

        after["tokenHoldUsd"] += token_delta
        after["positionUsd"] += position_delta
        after["borrowUsd"] += borrow_delta
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"]

        if borrow_delta > 0:
            warnings.append("Borrow value increases under this shock, reducing net worth.")
        if any(v < -15 for v in shocks.values()):
            warnings.append("Large downside shock can materially change liquidation and LP range risk.")

        return {
            "after": self._round_summary(after),
            "changes": changes,
            "warnings": warnings,
            "assumptions": ["Price shock is applied linearly to matching token exposures."],
        }

    def _simulate_lend(self, before: dict, assets: list[dict], payload: dict, action: str, fee_model: dict) -> dict:
        symbol = self.pricing.normalize_symbol(payload.get("symbol") or "ETH")
        amount = float(payload.get("amount") or 0)
        price = self.pricing.get_price_safe(symbol, 0.0)
        value = amount * price
        gas = float(payload.get("gasUsd") or fee_model["gas"].get(action) or self.DEFAULT_GAS_USD[action])
        market = self._market_from_payload(payload, symbol)
        apr = float(market.get("supplyApr") or market.get("apr") or market.get("pool_apr") or 0) if market else 0.0
        wallet_value = self._asset_value(assets, symbol)
        warnings = []

        if value > wallet_value:
            warnings.append(f"Wallet snapshot has less {symbol} than the simulated amount.")

        after = dict(before)
        after["tokenHoldUsd"] -= min(value, wallet_value)
        after["positionUsd"] += value
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"] - gas

        return {
            "after": self._round_summary(after),
            "changes": [
                {"label": f"Move {amount:g} {symbol} from wallet to {action}", "deltaUsd": round(value, 4)},
                {"label": "Estimated gas cost", "deltaUsd": -round(gas, 4)},
                {"label": "Projected annual income at current APR", "deltaUsd": round(value * apr / 100, 4)},
            ],
            "warnings": warnings,
            "assumptions": [
                f"APR uses current market data: {apr:.2f}%.",
                fee_model["source_note"],
                "No transaction is executed.",
            ],
        }

    def _simulate_borrow(self, before: dict, payload: dict, fee_model: dict) -> dict:
        symbol = self.pricing.normalize_symbol(payload.get("symbol") or "USDC")
        amount = float(payload.get("amount") or 0)
        price = self.pricing.get_price_safe(symbol, 0.0)
        value = amount * price
        gas = float(payload.get("gasUsd") or fee_model["gas"].get("borrow") or self.DEFAULT_GAS_USD["borrow"])
        market = self._market_from_payload(payload, symbol) or {}
        borrow_apr = float(payload.get("borrowApr") or market.get("borrowApr") or market.get("borrowStableApr") or 0.0)
        stress_shock_pct = float(payload.get("shockPct") or 20)
        stressed_debt = value * max(1 + stress_shock_pct / 100, 0)
        after = dict(before)
        after["tokenHoldUsd"] += max(value - gas, 0.0)
        after["borrowUsd"] += value
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"]
        warnings = []

        if before["positionUsd"] <= 0:
            warnings.append("No supplied collateral is visible in the latest portfolio snapshot.")
        if borrow_apr <= 0:
            warnings.append("Missing borrow APR from market data; borrowing cost can be understated.")

        return {
            "after": self._round_summary(after),
            "changes": [
                {"label": f"Borrow {amount:g} {symbol}", "deltaUsd": round(value, 4)},
                {"label": "Estimated gas cost", "deltaUsd": -round(gas, 4)},
                {"label": "Projected annual borrow cost", "deltaUsd": -round(value * borrow_apr / 100, 4)},
                {"label": f"Debt value after {stress_shock_pct:.1f}% {symbol} move", "deltaUsd": -round(stressed_debt - value, 4)},
            ],
            "warnings": warnings,
            "assumptions": [
                f"Borrow APR uses current market data: {borrow_apr:.2f}%.",
                f"Debt stress uses {stress_shock_pct:.1f}% price move on borrowed token.",
                "Health factor depends on existing collateral thresholds and should be checked before execution.",
                fee_model["source_note"],
            ],
            "strategy": {
                "name": "borrow",
                "symbol": symbol,
                "borrowValueUsd": round(value, 4),
                "borrowApr": round(borrow_apr, 4),
                "gasUsd": round(gas, 4),
                "stressedDebtUsd": round(stressed_debt, 4),
            },
        }

    def _simulate_swap(self, before: dict, assets: list[dict], payload: dict, fee_model: dict) -> dict:
        from_symbol = self.pricing.normalize_symbol(payload.get("fromSymbol") or payload.get("symbol") or "ETH")
        to_symbol = self.pricing.normalize_symbol(payload.get("toSymbol") or "USDC")
        amount = float(payload.get("amount") or 0)
        from_price = self.pricing.get_price_safe(from_symbol, 0.0)
        to_price = self.pricing.get_price_safe(to_symbol, 0.0)
        value = amount * from_price
        gas = float(payload.get("gasUsd") or fee_model["gas"].get("swap") or self.DEFAULT_GAS_USD["swap"])
        slippage_pct = float(payload.get("slippagePct") or 0.3)
        protocol_fee_pct = float(payload.get("protocolFeePct") or fee_model["protocol"].get("swap_fee_pct") or 0.3)
        total_trade_fee_pct = slippage_pct + protocol_fee_pct
        received_value = value * (1 - total_trade_fee_pct / 100)
        received_amount = received_value / to_price if to_price > 0 else 0.0
        wallet_value = self._asset_value(assets, from_symbol)
        after = dict(before)
        after["tokenHoldUsd"] += received_value - min(value, wallet_value) - gas
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"]
        warnings = []

        if value > wallet_value:
            warnings.append(f"Wallet snapshot has less {from_symbol} than the simulated swap amount.")

        return {
            "after": self._round_summary(after),
            "changes": [
                {"label": f"Sell {amount:g} {from_symbol}", "deltaUsd": -round(value, 4)},
                {"label": f"Receive about {received_amount:.6g} {to_symbol}", "deltaUsd": round(received_value, 4)},
                {"label": "Estimated slippage", "deltaUsd": -round(value * slippage_pct / 100, 4)},
                {"label": "Estimated swap protocol fee", "deltaUsd": -round(value * protocol_fee_pct / 100, 4)},
                {"label": "Estimated gas cost", "deltaUsd": -round(gas, 4)},
            ],
            "warnings": warnings,
            "assumptions": [f"Slippage estimate: {slippage_pct:.2f}%.", f"Swap fee estimate: {protocol_fee_pct:.2f}%.", fee_model["source_note"]],
        }

    def _simulate_loop_lending(self, before: dict, assets: list[dict], payload: dict, fee_model: dict) -> dict:
        collateral_symbol = self.pricing.normalize_symbol(payload.get("collateralSymbol") or payload.get("symbol") or "ETH")
        borrow_symbol = self.pricing.normalize_symbol(payload.get("borrowSymbol") or "USDC")
        amount = float(payload.get("amount") or 0)
        loops = max(1, min(int(payload.get("loops") or 3), 10))
        collateral_price = self.pricing.get_price_safe(collateral_symbol, 0.0)
        initial_value = amount * collateral_price
        wallet_value = self._asset_value(assets, collateral_symbol)
        market = self._market_from_payload(payload, collateral_symbol) or {}
        borrow_market = self._best_market(borrow_symbol) or {}
        max_ltv = self._ratio(payload.get("maxLtv") or market.get("maxLtv") or market.get("maximumLTV"))
        liquidation_threshold = self._ratio(payload.get("liquidationThreshold") or market.get("liquidationThreshold"))
        target_ltv = self._ratio(payload.get("targetLtv"))
        warnings = []
        if max_ltv <= 0:
            max_ltv = 0.65
            warnings.append("Missing max LTV from market data; simulator used a fallback LTV assumption.")
        if liquidation_threshold <= 0 and max_ltv > 0:
            liquidation_threshold = min(max_ltv * 1.12, 0.95)
            warnings.append("Missing liquidation threshold from market data; simulator approximated threshold from max LTV.")
        if target_ltv <= 0:
            target_ltv = min(max_ltv * 0.8, liquidation_threshold * 0.72) if liquidation_threshold > 0 else max_ltv * 0.75
        target_ltv = max(0.0, min(target_ltv, max_ltv))
        supply_apr = float(payload.get("supplyApr") or market.get("supplyApr") or market.get("apr") or 0.0)
        borrow_apr = float(payload.get("borrowApr") or borrow_market.get("borrowApr") or borrow_market.get("borrowStableApr") or 0.0)
        swap_fee_pct = float(payload.get("swapFeePct") or fee_model["protocol"].get("swap_fee_pct") or 0.3)
        slippage_pct = float(payload.get("slippagePct") or 0.3)
        gas_per_step = float(payload.get("gasUsd") or fee_model["gas"].get("loop_step") or self.DEFAULT_GAS_USD["lend"] + self.DEFAULT_GAS_USD["swap"])
        stress_shock_pct = float(payload.get("shockPct") or -20)

        total_supply = 0.0
        total_borrow = 0.0
        total_fees = 0.0
        current_collateral = min(initial_value, wallet_value) if wallet_value > 0 else initial_value
        steps = []

        for i in range(loops):
            supplied = current_collateral
            borrow_value = supplied * target_ltv
            trade_fee = borrow_value * (swap_fee_pct + slippage_pct) / 100
            step_fee = gas_per_step + trade_fee
            next_collateral = max(borrow_value - step_fee, 0.0)
            total_supply += supplied
            total_borrow += borrow_value
            total_fees += step_fee
            steps.append({
                "loop": i + 1,
                "suppliedUsd": round(supplied, 4),
                "borrowedUsd": round(borrow_value, 4),
                "feesUsd": round(step_fee, 4),
                "recycledCollateralUsd": round(next_collateral, 4),
            })
            current_collateral = next_collateral

        annual_supply_income = total_supply * supply_apr / 100
        annual_borrow_cost = total_borrow * borrow_apr / 100
        net_annual_income = annual_supply_income - annual_borrow_cost
        health_factor = (total_supply * liquidation_threshold / total_borrow) if total_borrow > 0 and liquidation_threshold > 0 else None
        stressed_health_factor = (
            total_supply * max(1 + stress_shock_pct / 100, 0) * liquidation_threshold / total_borrow
            if total_borrow > 0 and liquidation_threshold > 0
            else None
        )
        after = dict(before)
        after["tokenHoldUsd"] -= min(initial_value, wallet_value)
        after["positionUsd"] += total_supply
        after["borrowUsd"] += total_borrow
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"] - total_fees

        if initial_value > wallet_value:
            warnings.append(f"Wallet snapshot has less {collateral_symbol} than the simulated loop amount.")
        if target_ltv >= max_ltv * 0.98:
            warnings.append("Target LTV is very close to the protocol max LTV.")
        if health_factor is not None and health_factor < 1.25:
            warnings.append("Loop strategy creates a thin liquidation buffer.")
        if stressed_health_factor is not None and stressed_health_factor <= 1:
            warnings.append(f"Under a {stress_shock_pct:.1f}% collateral shock, health factor is near or below liquidation.")
        if net_annual_income < 0:
            warnings.append("Borrow cost is higher than supply income under current APRs.")

        return {
            "after": self._round_summary(after),
            "changes": [
                {"label": f"Total supplied after {loops} loops", "deltaUsd": round(total_supply, 4)},
                {"label": "Total borrowed", "deltaUsd": -round(total_borrow, 4)},
                {"label": "Estimated total fees", "deltaUsd": -round(total_fees, 4)},
                {"label": "Projected annual supply income", "deltaUsd": round(annual_supply_income, 4)},
                {"label": "Projected annual borrow cost", "deltaUsd": -round(annual_borrow_cost, 4)},
                {"label": "Projected annual net carry", "deltaUsd": round(net_annual_income, 4)},
            ],
            "warnings": warnings,
            "assumptions": [
                f"Loops: {loops}. Target LTV: {target_ltv * 100:.2f}%. Max LTV: {max_ltv * 100:.2f}%.",
                f"Supply APR: {supply_apr:.2f}%. Borrow APR: {borrow_apr:.2f}%.",
                f"Health factor after loop: {health_factor:.4f}." if health_factor else "Health factor unavailable due to missing threshold.",
                f"Stress health factor at {stress_shock_pct:.1f}% collateral move: {stressed_health_factor:.4f}." if stressed_health_factor else "Stress health factor unavailable.",
                fee_model["source_note"],
            ],
            "strategy": {
                "name": "loop_lending",
                "steps": steps,
                "totalSupplyUsd": round(total_supply, 4),
                "totalBorrowUsd": round(total_borrow, 4),
                "totalFeesUsd": round(total_fees, 4),
                "healthFactor": round(health_factor, 4) if health_factor else None,
                "stressHealthFactor": round(stressed_health_factor, 4) if stressed_health_factor else None,
                "netAnnualIncomeUsd": round(net_annual_income, 4),
            },
        }

    def _simulate_provide_liquidity(self, before: dict, assets: list[dict], payload: dict, fee_model: dict) -> dict:
        token0 = self.pricing.normalize_symbol(payload.get("token0") or payload.get("symbol") or "ETH")
        token1 = self.pricing.normalize_symbol(payload.get("token1") or payload.get("toSymbol") or "USDC")
        amount0 = float(payload.get("amount0") or payload.get("amount") or 0)
        amount1 = float(payload.get("amount1") or 0)
        price0 = self.pricing.get_price_safe(token0, 0.0)
        price1 = self.pricing.get_price_safe(token1, 0.0)
        value0 = amount0 * price0
        value1 = amount1 * price1 if amount1 > 0 else value0
        position_value = value0 + value1
        gas = float(payload.get("gasUsd") or fee_model["gas"].get("add_liquidity") or self.DEFAULT_GAS_USD["add_liquidity"])
        shock_pct = float(payload.get("shockPct") or -20)
        ratio = max(1 + shock_pct / 100, 0.0001)
        il_pct = (2 * sqrt(ratio) / (1 + ratio) - 1) * 100
        il_usd = position_value * il_pct / 100
        market = self._market_from_payload(payload) or self._best_pair_market(token0, token1) or {}
        apr = float(payload.get("apr") or market.get("total_apr") or market.get("pool_apr") or market.get("apr") or 0.0)
        projected_fee_income = position_value * apr / 100
        wallet0 = self._asset_value(assets, token0)
        wallet1 = self._asset_value(assets, token1)
        after = dict(before)
        after["tokenHoldUsd"] -= min(value0, wallet0) + min(value1, wallet1)
        after["positionUsd"] += position_value
        after["netWorthUsd"] = after["tokenHoldUsd"] + after["positionUsd"] - after["borrowUsd"] - gas
        warnings = [
            "LP simulation is assumption-based and does not calculate production LP/Farming PnL or fee/yield attribution."
        ]

        if value0 > wallet0:
            warnings.append(f"Wallet snapshot has less {token0} than the simulated LP amount.")
        if value1 > wallet1:
            warnings.append(f"Wallet snapshot has less {token1} than the simulated LP amount.")
        if apr <= 0:
            warnings.append("Missing LP APR from market data; projected fee income is unavailable.")
        if il_pct < -2:
            warnings.append("The configured price move creates meaningful impermanent loss for a 50/50 LP.")

        return {
            "after": self._round_summary(after),
            "changes": [
                {"label": f"Provide {token0}/{token1} liquidity", "deltaUsd": round(position_value, 4)},
                {"label": "Estimated add-liquidity gas cost", "deltaUsd": -round(gas, 4)},
                {"label": f"Estimated IL at {shock_pct:.1f}% {token0} move", "deltaUsd": round(il_usd, 4)},
                {"label": "Projected annual LP fee income", "deltaUsd": round(projected_fee_income, 4)},
            ],
            "warnings": warnings,
            "assumptions": [
                "LP model uses a 50/50 constant-product pool approximation.",
                "Dashboard LP/Farming PnL remains hidden until fee, yield, and liquidity-range attribution are reliable.",
                f"APR uses current pool data: {apr:.2f}%.",
                f"Impermanent loss estimate: {il_pct:.4f}%.",
                fee_model["source_note"],
            ],
            "strategy": {
                "name": "provide_liquidity",
                "pair": f"{token0}/{token1}",
                "positionValueUsd": round(position_value, 4),
                "impermanentLossPct": round(il_pct, 6),
                "impermanentLossUsd": round(il_usd, 4),
                "projectedAnnualFeeIncomeUsd": round(projected_fee_income, 4),
                "gasUsd": round(gas, 4),
            },
        }

    def _summary(self, latest: dict, assets: list[dict], positions: list[dict]) -> dict:
        token_hold = float(latest.get("token_hold_usd") or sum(float(a.get("value_usd") or 0) for a in assets))
        supply = float(latest.get("total_supply_usd") or 0)
        amm = float(latest.get("total_amm_usd") or 0)
        borrow = float(latest.get("total_borrow_usd") or 0)
        return self._round_summary({
            "netWorthUsd": float(latest.get("net_worth_usd") or token_hold + supply + amm - borrow),
            "tokenHoldUsd": token_hold,
            "positionUsd": supply + amm,
            "borrowUsd": borrow,
            "positionCount": len(positions),
        })

    def _round_summary(self, row: dict) -> dict:
        return {
            "netWorthUsd": round(float(row.get("netWorthUsd") or 0), 4),
            "tokenHoldUsd": round(float(row.get("tokenHoldUsd") or 0), 4),
            "positionUsd": round(float(row.get("positionUsd") or 0), 4),
            "borrowUsd": round(float(row.get("borrowUsd") or 0), 4),
            "positionCount": int(row.get("positionCount") or 0),
        }

    def _best_market(self, symbol: str) -> dict | None:
        markets = self.yield_repository.collection.find(
            {"$or": [{"asset": symbol}, {"symbol": symbol}]},
            {"_id": 0},
        ).sort("supplyApr", -1).limit(1)
        return next(markets, None)

    def _market_from_payload(self, payload: dict, symbol: str | None = None) -> dict | None:
        market_id = payload.get("marketId") or payload.get("market_id")
        if market_id:
            market = self.yield_repository.get_market_by_id(str(market_id))
            if market:
                return market
        if symbol:
            return self._best_market(symbol)
        return None

    def _best_pair_market(self, token0: str, token1: str) -> dict | None:
        pair_symbols = {f"{token0}/{token1}", f"{token1}/{token0}", f"{token0}-{token1}", f"{token1}-{token0}"}
        markets = self.yield_repository.collection.find(
            {
                "$or": [
                    {"symbol": {"$in": list(pair_symbols)}},
                    {"pair": {"$in": list(pair_symbols)}},
                    {"asset": {"$all": [token0, token1]}},
                    {"tokens": {"$all": [token0, token1]}},
                ],
            },
            {"_id": 0},
        ).sort("total_apr", -1).limit(1)
        return next(markets, None)

    def _asset_value(self, assets: list[dict], symbol: str) -> float:
        for asset in assets:
            if self.pricing.normalize_symbol(asset.get("symbol") or "") == symbol:
                return float(asset.get("value_usd") or 0)
        return 0.0

    def _fee_model(self, wallet: str) -> dict:
        stats = self.cashflow_repository.get_wallet_fee_stats(wallet)
        observed_gas = float(stats.get("median_gas_usd") or stats.get("avg_gas_usd") or 0.0)
        gas_base = observed_gas if observed_gas > 0 else self.DEFAULT_GAS_USD["swap"]
        source = "onchain_cashflow_median" if observed_gas > 0 else "default_fee_assumption"

        return {
            "source": source,
            "source_note": (
                f"Gas fee uses wallet on-chain average (${gas_base:.2f})."
                if observed_gas > 0
                else "Gas fee uses default estimate because no on-chain fee sample is available."
            ),
            "sampleCount": stats.get("sample_count", 0),
            "gas": {
                "swap": round(gas_base, 4),
                "lend": round(max(gas_base * 0.75, self.DEFAULT_GAS_USD["lend"]), 4),
                "stake": round(max(gas_base * 0.75, self.DEFAULT_GAS_USD["stake"]), 4),
                "borrow": round(max(gas_base, self.DEFAULT_GAS_USD["borrow"]), 4),
                "loop_step": round(max(gas_base * 1.8, self.DEFAULT_GAS_USD["lend"] + self.DEFAULT_GAS_USD["swap"]), 4),
                "add_liquidity": round(max(gas_base * 1.8, self.DEFAULT_GAS_USD["add_liquidity"]), 4),
            },
            "protocol": {
                "swap_fee_pct": 0.3,
            },
            "raw": stats,
        }

    def _ratio(self, value) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return parsed / 100 if parsed > 1 else parsed
