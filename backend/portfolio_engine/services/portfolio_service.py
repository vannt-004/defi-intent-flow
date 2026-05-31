from config import Web3Config
from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.user.wallet_service import WalletService
from portfolio_engine.services.position_service import PositionService
from shared.databases.mongo_client import MongoConnection


class PortfolioService:

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
        wallet_assets = self._get_asset()
        all_positions = await self._get_positions()

        supply_positions = []
        borrow_positions = []
        amm_positions = []

        for p in all_positions:
            side = getattr(p, "side", None) or p.get("side") if isinstance(
                p, dict
            ) else getattr(p, "side", None)
            p_type = getattr(p, "type", None) or p.get("type") if isinstance(
                p, dict
            ) else getattr(p, "type", None)

            if p_type == "amm":
                amm_positions.append(p)
            elif side == "COLLATERAL":
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
                "healthFactor": health_factor,
                "positionsCount": len(all_positions)
            },
            "allocations": allocations,
            "positions": [p.to_camel_dict() for p in all_positions],
            "assets": wallet_assets
        }

    async def _get_positions(self):
        return await self.position_service.get_positions(self.wallet)

    def _get_asset(self):
        return self.wallet_service.get_wallet_portfolio(self.wallet)

    def _sum_value(self, positions):
        return sum(p.get("value_usd", 0) if isinstance(p, dict) else getattr(p, "value_usd", 0) for p in positions)

    def _calculate_health_factor(self, supply_positions, borrow_positions):
        total_borrow = sum(
            p.get("value_usd", 0) if isinstance(p, dict) else getattr(p, "value_usd", 0)
            for p in borrow_positions
            )
        total_collateral = 0
        weighted_collateral = 0

        for p in supply_positions:
            val = p.get("value_usd", 0) if isinstance(p, dict) else getattr(p, "value_usd", 0)
            threshold = p.get("liquidation_threshold", 0.8) if isinstance(p, dict) else getattr(p, "liquidation_threshold", 0.8)
            total_collateral += val
            weighted_collateral += val * threshold

        if total_borrow == 0:
            return 999.0
        if total_collateral == 0:
            return 0.0

        return round(weighted_collateral / total_borrow, 2)

