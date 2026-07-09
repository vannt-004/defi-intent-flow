from config import Web3Config
from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.user.wallet_service import WalletService
from portfolio_engine.services.position_service import PositionService
from shared.databases.mongo_client import MongoConnection


class PortfolioService:
    MIN_DISPLAY_VALUE_USD = 0.01

    def __init__(self, wallet: str):
        self.wallet = wallet
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)
        self.position_service = PositionService()
        self.wallet_service = WalletService(
            w3=Web3Config.W3,
            multicall_address=Web3Config.MULTICALL_ADDRESS,
            pricing=self.pricing
        )

    async def get_data(self):
        wallet_assets = [
            asset for asset in self._get_asset()
            if float(asset.get("valueUsd") or 0) >= self.MIN_DISPLAY_VALUE_USD
        ]
        all_positions = [
            position for position in await self._get_positions()
            if self._position_value_usd(position) >= self.MIN_DISPLAY_VALUE_USD
        ]

        supply_positions = []
        borrow_positions = []
        amm_positions = []

        for p in all_positions:
            side = self._get_position_field(p, "side")
            p_type = self._get_position_field(p, "type")

            if p_type == "amm":
                amm_positions.append(p)
            elif side in ("LENDER", "COLLATERAL"):
                supply_positions.append(p)
            elif side == "BORROWER":
                borrow_positions.append(p)

        total_wallet_usd = sum(asset.get("valueUsd", 0) for asset in wallet_assets)
        total_supply_usd = self._sum_value(supply_positions)
        total_borrow_usd = self._sum_value(borrow_positions)
        total_amm_usd = self._sum_value(amm_positions)

        net_worth_usd = total_wallet_usd + total_supply_usd + total_amm_usd - total_borrow_usd
        health_factor = self._calculate_health_factor(
            supply_positions, borrow_positions
        )

        total_gross_assets = total_wallet_usd + total_supply_usd + total_amm_usd

        allocations = [
            {
                "purpose": "Wallet Balance",
                "valueUsd": round(total_wallet_usd, 2),
                "percentage": round(
                    (total_wallet_usd / total_gross_assets * 100), 2
                ) if total_gross_assets > 0 else 0
            }, {
                "purpose": "Lending (Supply)",
                "valueUsd": round(total_supply_usd, 2),
                "percentage": round(
                    (total_supply_usd / total_gross_assets * 100), 2
                ) if total_gross_assets > 0 else 0
            }, {
                "purpose": "AMM Liquidity",
                "valueUsd": round(total_amm_usd, 2),
                "percentage": round(
                    (total_amm_usd / total_gross_assets * 100), 2
                ) if total_gross_assets > 0 else 0
            }
        ]

        return {
            "summary": {
                "netWorthUsd": round(net_worth_usd, 2),
                "totalWalletUsd": round(total_wallet_usd, 2),
                "totalSupplyUsd": round(total_supply_usd, 2),
                "totalBorrowUsd": round(total_borrow_usd, 2),
                "totalAmmUsd": round(total_amm_usd, 2),
                "collateralUsd": round(self._collateral_value(supply_positions), 2),
                "healthFactor": health_factor,
                "positionCount": len(all_positions),
                "positionsCount": len(all_positions)
            },
            "allocations": allocations,
            "positions": [self._position_to_camel_dict(p) for p in all_positions],
            "assets": wallet_assets
        }

    async def get_preview_analytics(self, data: dict | None = None) -> dict:
        data = data or await self.get_data()
        summary = data.get("summary") or {}
        assets = data.get("assets") or []
        positions = data.get("positions") or []

        token_hold_usd = float(summary.get("totalWalletUsd") or 0)
        lending_usd = float(summary.get("totalSupplyUsd") or 0)
        debt_usd = float(summary.get("totalBorrowUsd") or 0)
        farming_usd = float(summary.get("totalAmmUsd") or 0)
        net_worth_usd = float(summary.get("netWorthUsd") or 0)

        return {
            "netWorth": {
                "totalUsd": round(net_worth_usd, 4),
                "tokenHoldUsd": round(token_hold_usd, 4),
                "lendingUsd": round(lending_usd, 4),
                "interestEarnedUsd": 0.0,
                "debtUsd": round(debt_usd, 4),
                "debtInterestUsd": 0.0,
                "farmingUsd": round(farming_usd, 4),
            },
            "pnlSummary": self._empty_pnl_summary(),
            "positionsPnL": self._build_preview_positions_pnl(assets, positions),
            "transactions": [],
            "transactionPoolGroups": [],
            "pnlFlows": [],
            "chartHistory": [{
                "timestamp": None,
                "label": "Now",
                "tokenHold": round(token_hold_usd, 4),
                "positions": round(lending_usd + farming_usd - debt_usd, 4),
                "netWorth": round(net_worth_usd, 4),
            }],
            "readModel": {
                "refreshMode": "guest_preview",
                "cashflowIncremental": False,
                "persisted": False,
            },
        }

    async def _get_positions(self):
        return await self.position_service.get_positions(self.wallet)

    def _get_asset(self):
        return self.wallet_service.get_wallet_portfolio(self.wallet)

    def _sum_value(self, positions):
        return sum(self._position_value_usd(position) for position in positions)

    def _get_position_field(self, position, key: str, default=None):
        if isinstance(position, dict):
            if key in position:
                return position.get(key, default)
            camel_key = self._snake_to_camel(key)
            return position.get(camel_key, default)
        return getattr(position, key, default)

    def _position_value_usd(self, position) -> float:
        return float(self._get_position_field(position, "value_usd", 0) or 0)

    def _snake_to_camel(self, key: str) -> str:
        if "_" not in key:
            return key
        parts = key.split("_")
        return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

    def _collateral_value(self, positions):
        total = 0.0
        for position in positions:
            if self._get_position_field(position, "is_collateral", False):
                total += self._position_value_usd(position)
        return total

    def _build_preview_positions_pnl(self, assets: list[dict], positions: list[dict]) -> list[dict]:
        rows = []

        for asset in assets:
            symbol = asset.get("symbol")
            if not symbol:
                continue
            value_usd = float(asset.get("valueUsd") or 0)
            balance = float(asset.get("balance") or 0)
            current_price = float(asset.get("price") or 0)
            rows.append({
                "positionId": f"hold-{symbol}",
                "name": symbol,
                "protocol": "Wallet",
                "type": "hold",
                "valueUsd": round(value_usd, 4),
                "balance": round(balance, 8),
                "costBasisUsd": 0.0,
                "entryPrice": None,
                "currentPrice": round(current_price, 8) if current_price else None,
                "pnlUsd": 0.0,
                "pnlPct": None,
                "pnlType": "unrealized",
                "pnlReliable": False,
                "pnlNote": "Preview mode does not persist cashflow, so token PnL is not calculated",
                "costBasisReliable": False,
                "healthFactor": 100,
                "apy": None,
            })

        for position in positions:
            side = position.get("side")
            is_amm = position.get("type") == "amm"
            position_type = "farm" if is_amm else ("borrow" if side == "BORROWER" else "lend")
            value_usd = float(position.get("valueUsd") or 0)
            balance = None if is_amm else float(position.get("balance") or 0)
            name = self._preview_position_name(position)
            current_price = value_usd / balance if balance and value_usd > 0 and not is_amm else None

            rows.append({
                "positionId": position.get("positionId") or position.get("marketId") or f"{position_type}-{name}",
                "name": name,
                "protocol": position.get("protocol") or "Protocol",
                "type": position_type,
                "valueUsd": round(-value_usd if side == "BORROWER" else value_usd, 4),
                "balance": round(balance, 8) if balance is not None else None,
                "token0": position.get("token0"),
                "token1": position.get("token1"),
                "amount0": position.get("amount0"),
                "amount1": position.get("amount1"),
                "costBasisUsd": 0.0,
                "entryPrice": None,
                "currentPrice": round(current_price, 8) if current_price else None,
                "pnlUsd": 0.0,
                "pnlPct": None,
                "pnlType": "yield" if is_amm else ("interest_cost" if side == "BORROWER" else "interest_earned"),
                "pnlReliable": False,
                "pnlNote": "Preview mode shows current value only; protocol PnL is not calculated",
                "costBasisReliable": False,
                "healthFactor": 100 if side != "BORROWER" else 50,
                "apy": float(position.get("borrowApr") or 0) if side == "BORROWER" else float(position.get("supplyApr") or 0),
            })

        return rows

    def _preview_position_name(self, position: dict) -> str:
        assets = position.get("asset") or []
        if position.get("type") == "amm":
            symbols = [symbol for symbol in assets if symbol]
            return "/".join(symbols) if symbols else position.get("rawSymbol") or "LP"
        return assets[0] if assets else position.get("rawSymbol") or "UNKNOWN"

    def _empty_pnl_summary(self) -> dict:
        return {
            "todayUsd": 0.0,
            "todayPct": 0.0,
            "sevenDayUsd": 0.0,
            "sevenDayPct": 0.0,
            "allTimeUsd": 0.0,
            "allTimePct": 0.0,
            "roiPct": 0.0,
        }

    def _position_to_camel_dict(self, position):
        if hasattr(position, "to_camel_dict"):
            return position.to_camel_dict()

        if not isinstance(position, dict):
            return position

        assets = self._get_position_field(position, "asset", []) or []
        is_amm = self._get_position_field(position, "type") == "amm"

        return {
            "type": self._get_position_field(position, "type"),
            "protocol": self._get_position_field(position, "protocol"),
            "positionId": self._get_position_field(position, "position_id"),
            "marketId": self._get_position_field(position, "market_id") or self._get_position_field(position, "pool_id"),
            "asset": assets,
            "rawSymbol": "/".join(assets),
            "balance": None if is_amm else self._get_position_field(position, "balance", 0),
            "valueUsd": self._position_value_usd(position),
            "side": self._get_position_field(position, "side") or "LP",
            "isCollateral": self._get_position_field(position, "is_collateral", False),
            "maxLtv": self._get_position_field(position, "max_ltv", 0),
            "liquidationThreshold": self._get_position_field(position, "liquidation_threshold", 0),
            "supplyApr": self._get_position_field(position, "supply_apr", 0),
            "borrowApr": self._get_position_field(position, "borrow_apr", 0),
            "borrowStableApr": self._get_position_field(position, "borrow_stable_apr", 0),
            "token0": assets[0] if assets else None,
            "token1": assets[1] if len(assets) > 1 else None,
            "amount0": self._get_position_field(position, "amount0"),
            "amount1": self._get_position_field(position, "amount1"),
            "feeTier": self._get_position_field(position, "fee_tier"),
            "collectedFeeUsd": self._get_position_field(position, "collected_fee_usd"),
        }

    def _calculate_health_factor(self, supply_positions, borrow_positions):
        total_borrow = sum(
            self._position_value_usd(p)
            for p in borrow_positions
            )
        total_collateral = 0
        weighted_collateral = 0

        for p in supply_positions:
            val = self._position_value_usd(p)
            threshold = self._get_position_field(p, "liquidation_threshold", 0.8)
            total_collateral += val
            weighted_collateral += val * threshold

        if total_borrow == 0:
            return 999.0
        if total_collateral == 0:
            return 0.0

        return round(weighted_collateral / total_borrow, 2)
