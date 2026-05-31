# data_engine/services/user/portfolio_sync_service.py
from datetime import datetime, timezone
from typing import Any

from config import Web3Config
from data_engine.providers.the_graph.lending_factory import LendingProviderFactory  # Import factory mới
from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.user.wallet_service import WalletService
from portfolio_engine.services.position_service import PositionService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.asset_snapshot_repository import AssetSnapshotRepository
from shared.repositories.cashflow_repository import CashflowRepository
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository
from shared.repositories.wallet_repository import WalletRepository
from shared.utils.logger_utils import get_logger


class PortfolioSyncService:

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)

        self.wallet_repository = WalletRepository(self.db)
        self.asset_snapshot_repository = AssetSnapshotRepository(self.db)
        self.position_snapshot_repository = PositionSnapshotRepository(self.db)
        self.cashflow_repository = CashflowRepository(self.db)
        self.portfolio_repository = PortfolioRepository(self.db)

        self.wallet_service = WalletService(
            w3=Web3Config.W3,
            multicall_address=Web3Config.MULTICALL_ADDRESS,
            pricing=self.pricing, )
        self.position_service = PositionService()

        self.lending_factory = LendingProviderFactory(self.pricing)

    async def sync_user(self, wallet: str) -> dict:
        wallet = wallet.lower().strip()
        timestamp = int(datetime.now(timezone.utc).timestamp())

        self.wallet_repository.add_wallet(wallet)

        previous = self.portfolio_repository.get_latest_snapshot(wallet)
        last_sync_ts = int(previous.get("timestamp")) if previous and previous.get(
            "timestamp"
        ) else None

        assets = self.wallet_service.get_wallet_portfolio(wallet)

        positions = []
        new_actions = []

        for provider in self.lending_factory.get_all_providers():
            provider_name = provider.__class__.__name__
            try:
                prov_positions = await provider.get_positions(wallet)
                positions.extend(prov_positions)

                new_deposits = await provider.get_deposits(
                    wallet, from_ts=last_sync_ts, limit=1000
                )
                new_withdraws = await provider.get_withdraws(
                    wallet, from_ts=last_sync_ts, limit=1000
                )
                new_borrows = await provider.get_borrows(
                    wallet, from_ts=last_sync_ts, limit=1000
                )
                new_repays = await provider.get_repays(
                    wallet, from_ts=last_sync_ts, limit=1000
                )

                new_actions.extend(
                    new_deposits + new_withdraws + new_borrows + new_repays
                )
            except Exception as e:
                self.logger.error(
                    f"[PortfolioSyncService] Error fetching data from provider {provider_name}: {e}"
                )

        if new_actions:
            self._save_cashflows(wallet, new_actions)

        historical_cashflows = self.cashflow_repository.get_wallet_cashflows(wallet)
        all_cashflow_stats = self._calculate_historical_cashflow(historical_cashflows)

        # 5. Xây dựng và Lưu trữ Asset Snapshots (Bao gồm token_holding PnL)
        asset_rows, token_hold_usd, token_hold_pnl_usd = self._build_asset_snapshots(
            wallet=wallet, timestamp=timestamp, assets=assets
        )
        if asset_rows:
            self.asset_snapshot_repository.bulk_insert(asset_rows)

        # 6. Xây dựng và Lưu trữ Position Snapshots (Bao gồm Lending/AMM positions)
        (position_rows,
         total_supply_usd,
         total_borrow_usd,
         total_amm_usd,
         collateral_usd,
         position_pnl_usd,) = self._build_position_snapshots(
            wallet=wallet,
            timestamp=timestamp,
            positions=positions,
            cashflow=all_cashflow_stats, )
        if position_rows:
            self.position_snapshot_repository.bulk_insert(position_rows)

        supply_principal_usd = all_cashflow_stats["deposit_usd"] - all_cashflow_stats[
            "withdraw_usd"]
        borrow_principal_usd = all_cashflow_stats["borrow_usd"] - all_cashflow_stats[
            "repay_usd"]

        supply_interest_usd = total_supply_usd - supply_principal_usd
        borrow_interest_usd = total_borrow_usd - borrow_principal_usd
        net_interest_usd = supply_interest_usd - borrow_interest_usd

        net_worth_usd = (
            token_hold_usd + supply_principal_usd + total_amm_usd + supply_interest_usd - total_borrow_usd)

        previous_net_worth = float(
            previous.get("net_worth_usd") or 0.0
        ) if previous else 0.0
        total_pnl_usd = net_worth_usd - previous_net_worth if previous else 0.0

        # 8. Đóng gói snapshot tổng kết Portfolio toàn diện
        snapshot = {
            "wallet": wallet,
            "timestamp": timestamp,
            "position_count": len(positions),
            "asset_count": len(assets),
            "net_worth_usd": round(net_worth_usd, 4),
            "previous_net_worth_usd": round(previous_net_worth, 4),
            "total_pnl_usd": round(total_pnl_usd, 4),
            "token_hold_usd": round(token_hold_usd, 4),
            "token_hold_pnl_usd": round(token_hold_pnl_usd, 4),
            "total_supply_usd": round(total_supply_usd, 4),
            "supply_principal_usd": round(supply_principal_usd, 4),
            "supply_interest_usd": round(supply_interest_usd, 4),
            "total_borrow_usd": round(total_borrow_usd, 4),
            "borrow_principal_usd": round(borrow_principal_usd, 4),
            "borrow_interest_usd": round(borrow_interest_usd, 4),
            "net_interest_usd": round(net_interest_usd, 4),
            "total_amm_usd": round(total_amm_usd, 4),
            "collateral_usd": round(collateral_usd, 4),
            "position_pnl_usd": round(position_pnl_usd, 4),
            "cashflow": all_cashflow_stats,
            "created_at": datetime.now(timezone.utc),
        }

        self.portfolio_repository.insert_snapshot(snapshot)
        self.logger.info(
            "[PortfolioSyncService] Multi-Protocol Sync Done: wallet=%s net_worth=$%.2f pnl=$%.2f",
            wallet,
            net_worth_usd,
            total_pnl_usd, )

        return snapshot

    def _build_asset_snapshots(self, wallet: str, timestamp: int, assets: list[dict]) -> \
        tuple[list[dict], float, float]:
        rows = []
        total_value = 0.0
        total_pnl = 0.0

        for asset in assets:
            symbol = asset.get("symbol")
            if not symbol:
                continue

            value_usd = float(asset.get("valueUsd") or asset.get("value_usd") or 0)
            previous = self.asset_snapshot_repository.get_latest_asset_snapshot(
                wallet, symbol
            )
            previous_value = float(previous.get("value_usd") or 0) if previous else 0.0
            pnl_usd = value_usd - previous_value if previous else 0.0
            pnl_pct = (pnl_usd / previous_value * 100) if previous_value > 0 else 0.0

            row = {
                "wallet": wallet,
                "timestamp": timestamp,
                "symbol": symbol,
                "name": asset.get("name"),
                "address": asset.get("address"),
                "type": asset.get("type"),
                "balance": float(asset.get("balance") or 0),
                "balance_raw": asset.get("balanceRaw") or asset.get("balance_raw"),
                "decimals": int(asset.get("decimals") or 18),
                "price": float(asset.get("price") or 0),
                "value_usd": round(value_usd, 4),
                "previous_value_usd": round(previous_value, 4),
                "pnl_usd": round(pnl_usd, 4),
                "pnl_pct": round(pnl_pct, 4),
            }
            rows.append(row)
            total_value += value_usd
            total_pnl += pnl_usd

        return rows, total_value, total_pnl

    def _build_position_snapshots(self,
                                  wallet: str,
                                  timestamp: int,
                                  positions: list[Any],
                                  cashflow: dict) -> tuple[
        list[dict], float, float, float, float, float]:
        rows = []
        total_supply_usd = 0.0
        total_borrow_usd = 0.0
        total_amm_usd = 0.0
        collateral_usd = 0.0

        for position in positions:
            side = self._get(position, "side")
            position_type = self._get(position, "type")
            value_usd = float(self._get(position, "value_usd", 0) or 0)

            if position_type == "amm":
                total_amm_usd += value_usd
            elif side in ("LENDER", "COLLATERAL"):
                total_supply_usd += value_usd
            elif side == "BORROWER":
                total_borrow_usd += value_usd

            if bool(self._get(position, "is_collateral", False)):
                collateral_usd += value_usd

            position_id = self._get(position, "position_id")
            previous = self.position_snapshot_repository.get_latest_position_snapshot(
                wallet=wallet, position_id=position_id
            ) if position_id else None
            previous_value = float(previous.get("value_usd") or 0) if previous else 0.0
            pnl_usd = value_usd - previous_value if previous else 0.0
            pnl_pct = (pnl_usd / previous_value * 100) if previous_value > 0 else 0.0

            rows.append(
                {
                    "wallet": wallet,
                    "timestamp": timestamp,
                    "protocol": self._get(position, "protocol"),
                    "position_id": position_id,
                    "market_id": self._get(position, "market_id"),
                    "symbol": self._first(self._get(position, "asset")),
                    "side": side,
                    "type": position_type,
                    "balance": self._get(position, "balance", 0),
                    "value_usd": round(value_usd, 4),
                    "previous_value_usd": round(previous_value, 4),
                    "pnl_usd": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "supply_apr": self._get(position, "supply_apr", 0),
                    "borrow_apr": self._get(position, "borrow_apr", 0),
                    "is_collateral": bool(self._get(position, "is_collateral", False)),
                }
            )

        supply_principal = cashflow["deposit_usd"] - cashflow["withdraw_usd"]
        borrow_principal = cashflow["borrow_usd"] - cashflow["repay_usd"]
        position_pnl_usd = (total_supply_usd - supply_principal) - (
            total_borrow_usd - borrow_principal)

        return (rows,
                total_supply_usd,
                total_borrow_usd,
                total_amm_usd,
                collateral_usd,
                position_pnl_usd,)

    def _save_cashflows(self, wallet: str, actions: list[dict]):
        rows = []
        for action in actions:
            rows.append(
                {
                    "wallet": wallet,
                    "tx_id": action["tx_id"],
                    "timestamp": action["timestamp"],
                    "action": action["action"],
                    "market_id": action["market_id"],
                    "symbol": action["symbol"],
                    "amount": action["amount"],
                    "amount_usd": action["amount_usd"],
                }
            )
        self.cashflow_repository.bulk_upsert(rows)

    def _calculate_historical_cashflow(self, historical_actions: list[dict]) -> dict:
        deposit_usd = 0.0
        withdraw_usd = 0.0
        borrow_usd = 0.0
        repay_usd = 0.0

        for x in historical_actions:
            action = x.get("action", "").lower()
            amt = float(x.get("amount_usd") or 0)
            if action == "deposit":
                deposit_usd += amt
            elif action == "withdraw":
                withdraw_usd += amt
            elif action == "borrow":
                borrow_usd += amt
            elif action == "repay":
                repay_usd += amt

        return {
            "deposit_usd": round(deposit_usd, 4),
            "withdraw_usd": round(withdraw_usd, 4),
            "borrow_usd": round(borrow_usd, 4),
            "repay_usd": round(repay_usd, 4),
        }

    def _get(self, item: Any, key: str, default=None):
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def _first(self, value):
        if isinstance(value, list):
            return value[0] if value else None
        return value
