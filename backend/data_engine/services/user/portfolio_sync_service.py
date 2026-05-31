from datetime import datetime, timezone, timedelta
from typing import Any

from config import Web3Config
from data_engine.providers.the_graph.lending_factory import LendingProviderFactory
from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.user.onchain_transaction_crawler import OnchainTransactionCrawler
from data_engine.services.user.wallet_service import WalletService
from portfolio_engine.services.position_risk_service import PositionRiskService
from portfolio_engine.services.position_service import PositionService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.asset_snapshot_repository import AssetSnapshotRepository
from shared.repositories.cashflow_repository import CashflowRepository
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository
from shared.repositories.wallet_repository import WalletRepository
from shared.repositories.yield_snapshot_repository import YieldSnapshotRepository
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
        self.yield_snapshot_repository = YieldSnapshotRepository(self.db)

        self.wallet_service = WalletService(
            w3=Web3Config.W3,
            multicall_address=Web3Config.MULTICALL_ADDRESS,
            pricing=self.pricing, )
        self.position_service = PositionService()
        self.lending_factory = LendingProviderFactory(self.pricing)

    async def sync_user(self, wallet: str, mode: str = "SYNC") -> dict:
        wallet = wallet.lower().strip()
        self.wallet_repository.collection.update_one(
            {"wallet": wallet},
            {"$set": {"_id": wallet, "wallet": wallet, "status": "syncing", "isActive": False, "updatedAt": datetime.now(timezone.utc)}},
            upsert=True,
        )
        now_dt = datetime.now(timezone.utc)
        timestamp = int(now_dt.timestamp())

        previous = self.portfolio_repository.get_latest_snapshot(wallet)

        if mode == "CRAWL_NEW_USER":
            one_year_ago_dt = now_dt - timedelta(days=365)
            last_sync_ts = int(one_year_ago_dt.timestamp())
            self.logger.info(
                f"[Sync] Detect INITIAL MODE for wallet: {wallet}. "
                f"Setting historical sync timestamp to 1 year ago: {one_year_ago_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
        else:
            last_sync_ts = int(previous.get("timestamp")) if previous and previous.get(
                "timestamp"
            ) else int((now_dt - timedelta(days=365)).timestamp())

        assets = self.wallet_service.get_wallet_portfolio(wallet)

        positions = []
        new_actions = []

        for provider in self.lending_factory.get_all_providers():
            provider_name = provider.__class__.__name__
            try:
                prov_positions = await provider.get_positions(wallet)
                positions.extend(prov_positions)

                new_deposits = await provider.get_deposits(wallet, from_ts=last_sync_ts, limit=1000)
                new_withdraws = await provider.get_withdraws(wallet, from_ts=last_sync_ts, limit=1000)
                new_borrows = await provider.get_borrows(wallet, from_ts=last_sync_ts, limit=1000)
                new_repays = await provider.get_repays(wallet, from_ts=last_sync_ts, limit=1000)

                new_actions.extend(new_deposits + new_withdraws + new_borrows + new_repays)
            except Exception as e:
                self.logger.error(f"Error fetching data from provider {provider_name}: {e}" )

        if new_actions:
            self._save_cashflows(wallet, new_actions)

        start_block = 0 if mode == "CRAWL_NEW_USER" else None
        onchain_saved = await self._sync_onchain_cashflows(
            wallet=wallet,
            start_block=start_block,
        )

        historical_cashflows = self.cashflow_repository.get_all_wallet_cashflows(wallet)
        all_cashflow_stats = self._calculate_historical_cashflow(historical_cashflows)

        if mode == "CRAWL_NEW_USER" and not previous:
            self._backfill_synthetic_snapshots_7d(
                wallet=wallet,
                current_timestamp=timestamp,
                assets=assets,
                positions=positions,
                cashflows=historical_cashflows,
            )

        asset_rows, token_hold_usd, token_hold_pnl_usd = self._build_asset_snapshots(
            wallet=wallet, timestamp=timestamp, assets=assets
        )
        if asset_rows:
            self.asset_snapshot_repository.bulk_insert(asset_rows)

        (position_rows,
         total_supply_usd,
         total_borrow_usd,
         total_amm_usd,
         collateral_usd,
         position_pnl_usd) = self._build_position_snapshots(
            wallet=wallet,
            timestamp=timestamp,
            positions=positions,
            cashflow=all_cashflow_stats
        )
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
            "onchain_transaction_count": onchain_saved,
            "created_at": datetime.now(timezone.utc),
        }

        self.portfolio_repository.insert_snapshot(snapshot)

        try:
            PositionRiskService().get_wallet_risk(wallet, persist=True)
        except Exception as exc:
            self.logger.warning(f"Risk snapshot skipped wallet={wallet}: {exc}")

        self.wallet_repository.add_wallet(wallet)

        self.logger.info(
            "Multi-Protocol Sync Completed: wallet=%s net_worth=$%.2f pnl=$%.2f",
            wallet,
            net_worth_usd,
            total_pnl_usd
        )

        return snapshot

    def reset_wallet_data(self, wallet: str) -> dict:
        wallet = wallet.lower().strip()
        collections = {
            "portfolio_snapshot": self.db["portfolio_snapshot"],
            "asset_snapshot": self.db["asset_snapshot"],
            "position_snapshot": self.db["position_snapshot"],
            "cashflow": self.db["cashflow"],
            "onchain_transactions": self.db["onchain_transactions"],
            "position_risk_snapshot": self.db["position_risk_snapshot"],
        }
        deleted = {}
        for name, collection in collections.items():
            result = collection.delete_many({"wallet": wallet})
            deleted[name] = result.deleted_count
        return {"wallet": wallet, "deleted": deleted}

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
            previous = self.position_snapshot_repository.get_latest_position_snapshot(wallet, position_id) if position_id else None
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
                    "pool_id": self._get(position, "pool_id"),
                    "symbol": self._first(self._get(position, "asset")),
                    "asset": self._get(position, "asset") or [],
                    "side": side,
                    "type": position_type,
                    "balance": self._get(position, "balance", 0),
                    "value_usd": round(value_usd, 4),
                    "previous_value_usd": round(previous_value, 4),
                    "pnl_usd": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "estimated_interest_usd": 0.0,
                    "supply_apr": self._get(position, "supply_apr", 0),
                    "borrow_apr": self._get(position, "borrow_apr", 0),
                    "borrow_stable_apr": self._get(position, "borrow_stable_apr", 0),
                    "is_collateral": bool(self._get(position, "is_collateral", False)),
                    "max_ltv": self._get(position, "max_ltv", 0),
                    "liquidation_threshold": self._get(position, "liquidation_threshold", 0),
                    "amount0": self._get(position, "amount0"),
                    "amount1": self._get(position, "amount1"),
                    "deposited_token0": self._get(position, "deposited_token0"),
                    "deposited_token1": self._get(position, "deposited_token1"),
                    "withdrawn_token0": self._get(position, "withdrawn_token0"),
                    "withdrawn_token1": self._get(position, "withdrawn_token1"),
                    "token0_price": self._get(position, "token0_price"),
                    "token1_price": self._get(position, "token1_price"),
                    "tick_lower": self._get(position, "tick_lower"),
                    "tick_upper": self._get(position, "tick_upper"),
                    "fee_tier": self._get(position, "fee_tier"),
                    "collected_fee_usd": self._get(position, "collected_fee_usd", 0),
                    "assets_metadata": self._get(position, "assets_metadata") or [],
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
                position_pnl_usd)

    def _backfill_synthetic_snapshots_7d(
        self,
        wallet: str,
        current_timestamp: int,
        assets: list[dict],
        positions: list[Any],
        cashflows: list[dict],
    ):
        day_start = current_timestamp // 86400 * 86400
        for offset in range(7, 0, -1):
            snapshot_ts = day_start - offset * 86400
            cashflows_until_snapshot = [
                row for row in cashflows
                if int(row.get("timestamp") or 0) <= snapshot_ts
            ]
            self._backfill_synthetic_snapshot(
                wallet=wallet,
                timestamp=snapshot_ts,
                assets=assets,
                positions=positions,
                cashflow=self._calculate_historical_cashflow(cashflows_until_snapshot),
                all_cashflows=cashflows,
            )

    def _backfill_synthetic_snapshot(
        self,
        wallet: str,
        timestamp: int,
        assets: list[dict],
        positions: list[Any],
        cashflow: dict,
        all_cashflows: list[dict],
    ):
        asset_rows = []
        token_hold_usd = 0.0

        for asset in assets:
            symbol = asset.get("symbol")
            if not symbol:
                continue
            balance = self._historical_asset_balance(
                current_balance=float(asset.get("balance") or 0),
                symbol=symbol,
                timestamp=timestamp,
                cashflows=all_cashflows,
            )
            historical_price = self.pricing.get_historical_price(symbol, timestamp)
            if historical_price <= 0:
                historical_price = float(asset.get("price") or 0)
            value_usd = balance * historical_price
            token_hold_usd += value_usd
            asset_rows.append({
                "wallet": wallet,
                "timestamp": timestamp,
                "symbol": symbol,
                "name": asset.get("name"),
                "address": asset.get("address"),
                "type": asset.get("type"),
                "balance": balance,
                "balance_raw": asset.get("balanceRaw") or asset.get("balance_raw"),
                "decimals": int(asset.get("decimals") or 18),
                "price": float(historical_price or 0),
                "value_usd": round(value_usd, 4),
                "previous_value_usd": 0.0,
                "pnl_usd": 0.0,
                "pnl_pct": 0.0,
                "is_synthetic": True,
                "snapshot_source": "synthetic_7d_backfill",
            })

        position_rows = []
        total_supply_usd = 0.0
        total_borrow_usd = 0.0
        total_amm_usd = 0.0
        collateral_usd = 0.0

        for position in positions:
            side = self._get(position, "side")
            position_type = self._get(position, "type")
            symbol = self._first(self._get(position, "asset"))
            balance = self._historical_position_balance(
                position=position,
                current_balance=float(self._get(position, "balance", 0) or 0),
                symbol=symbol,
                timestamp=timestamp,
                cashflows=all_cashflows,
            )
            value_usd = self._historical_position_value(position, symbol, balance, timestamp)
            yield_snapshot = self._historical_yield_snapshot(position, timestamp)

            if position_type == "amm":
                total_amm_usd += value_usd
            elif side in ("LENDER", "COLLATERAL"):
                total_supply_usd += value_usd
            elif side == "BORROWER":
                total_borrow_usd += value_usd

            if bool(self._get(position, "is_collateral", False)):
                collateral_usd += value_usd

            position_rows.append({
                "wallet": wallet,
                "timestamp": timestamp,
                "protocol": self._get(position, "protocol"),
                "position_id": self._get(position, "position_id"),
                "market_id": self._get(position, "market_id"),
                "pool_id": self._get(position, "pool_id"),
                "symbol": symbol,
                "asset": self._get(position, "asset") or [],
                "side": side,
                "type": position_type,
                "balance": balance,
                "value_usd": round(value_usd, 4),
                "previous_value_usd": 0.0,
                "pnl_usd": 0.0,
                "pnl_pct": 0.0,
                "estimated_interest_usd": 0.0,
                "supply_apr": yield_snapshot.get("supply_apr", self._get(position, "supply_apr", 0)),
                "borrow_apr": yield_snapshot.get("borrow_apr", self._get(position, "borrow_apr", 0)),
                "borrow_stable_apr": yield_snapshot.get("borrow_stable_apr", self._get(position, "borrow_stable_apr", 0)),
                "is_collateral": bool(self._get(position, "is_collateral", False)),
                "max_ltv": yield_snapshot.get("max_ltv", self._get(position, "max_ltv", 0)),
                "liquidation_threshold": yield_snapshot.get("liquidation_threshold", self._get(position, "liquidation_threshold", 0)),
                "amount0": self._get(position, "amount0"),
                "amount1": self._get(position, "amount1"),
                "deposited_token0": self._get(position, "deposited_token0"),
                "deposited_token1": self._get(position, "deposited_token1"),
                "withdrawn_token0": self._get(position, "withdrawn_token0"),
                "withdrawn_token1": self._get(position, "withdrawn_token1"),
                "token0_price": self._get(position, "token0_price"),
                "token1_price": self._get(position, "token1_price"),
                "tick_lower": self._get(position, "tick_lower"),
                "tick_upper": self._get(position, "tick_upper"),
                "fee_tier": self._get(position, "fee_tier"),
                "collected_fee_usd": self._get(position, "collected_fee_usd", 0),
                "assets_metadata": self._get(position, "assets_metadata") or [],
                "is_synthetic": True,
                "snapshot_source": "synthetic_7d_backfill",
            })

        supply_principal_usd = cashflow["deposit_usd"] - cashflow["withdraw_usd"]
        borrow_principal_usd = cashflow["borrow_usd"] - cashflow["repay_usd"]
        supply_interest_usd = total_supply_usd - supply_principal_usd
        borrow_interest_usd = total_borrow_usd - borrow_principal_usd
        net_interest_usd = supply_interest_usd - borrow_interest_usd
        net_worth_usd = token_hold_usd + total_supply_usd + total_amm_usd - total_borrow_usd

        if asset_rows:
            self.asset_snapshot_repository.bulk_upsert(asset_rows)
        if position_rows:
            self.position_snapshot_repository.bulk_upsert(position_rows)
        self.portfolio_repository.upsert_snapshot({
            "wallet": wallet,
            "timestamp": timestamp,
            "position_count": len(positions),
            "asset_count": len(assets),
            "net_worth_usd": round(net_worth_usd, 4),
            "previous_net_worth_usd": 0.0,
            "total_pnl_usd": 0.0,
            "token_hold_usd": round(token_hold_usd, 4),
            "token_hold_pnl_usd": 0.0,
            "total_supply_usd": round(total_supply_usd, 4),
            "supply_principal_usd": round(supply_principal_usd, 4),
            "supply_interest_usd": round(supply_interest_usd, 4),
            "total_borrow_usd": round(total_borrow_usd, 4),
            "borrow_principal_usd": round(borrow_principal_usd, 4),
            "borrow_interest_usd": round(borrow_interest_usd, 4),
            "net_interest_usd": round(net_interest_usd, 4),
            "total_amm_usd": round(total_amm_usd, 4),
            "collateral_usd": round(collateral_usd, 4),
            "position_pnl_usd": 0.0,
            "cashflow": cashflow,
            "onchain_transaction_count": 0,
            "is_synthetic": True,
            "snapshot_source": "synthetic_7d_backfill",
            "created_at": datetime.now(timezone.utc),
        })

    def _historical_asset_balance(self, current_balance: float, symbol: str, timestamp: int, cashflows: list[dict]) -> float:
        balance = current_balance
        normalized_symbol = self.pricing.normalize_symbol(symbol)
        for row in cashflows:
            if self.pricing.normalize_symbol(row.get("symbol") or "") != normalized_symbol:
                continue
            if int(row.get("timestamp") or 0) <= timestamp:
                continue
            action = str(row.get("action") or "").lower()
            amount = float(row.get("amount") or 0)
            if action in ("transfer_in", "withdraw", "borrow", "buy"):
                balance -= amount
            elif action in ("transfer_out", "deposit", "repay", "sell"):
                balance += amount
        return max(balance, 0.0)

    def _historical_position_balance(self, position: Any, current_balance: float, symbol: str, timestamp: int, cashflows: list[dict]) -> float:
        if self._get(position, "type") == "amm":
            return current_balance

        balance = current_balance
        normalized_symbol = self.pricing.normalize_symbol(symbol)
        side = self._get(position, "side")
        for row in cashflows:
            if self.pricing.normalize_symbol(row.get("symbol") or "") != normalized_symbol:
                continue
            if int(row.get("timestamp") or 0) <= timestamp:
                continue
            action = str(row.get("action") or "").lower()
            amount = float(row.get("amount") or 0)
            if side in ("LENDER", "COLLATERAL"):
                if action == "deposit":
                    balance -= amount
                elif action == "withdraw":
                    balance += amount
            elif side == "BORROWER":
                if action == "borrow":
                    balance -= amount
                elif action == "repay":
                    balance += amount
        return max(balance, 0.0)

    def _historical_position_value(self, position: Any, symbol: str, balance: float, timestamp: int) -> float:
        if self._get(position, "type") == "amm":
            amount0 = float(self._get(position, "amount0", 0) or 0)
            amount1 = float(self._get(position, "amount1", 0) or 0)
            assets_metadata = self._get(position, "assets_metadata") or []
            symbol0 = assets_metadata[0].get("symbol") if len(assets_metadata) > 0 and isinstance(assets_metadata[0], dict) else None
            symbol1 = assets_metadata[1].get("symbol") if len(assets_metadata) > 1 and isinstance(assets_metadata[1], dict) else None
            price0 = self.pricing.get_historical_price(symbol0, timestamp) if symbol0 else float(self._get(position, "token0_price", 0) or 0)
            price1 = self.pricing.get_historical_price(symbol1, timestamp) if symbol1 else float(self._get(position, "token1_price", 0) or 0)
            return amount0 * price0 + amount1 * price1

        price = self.pricing.get_historical_price(symbol, timestamp)
        if price <= 0:
            current_value = float(self._get(position, "value_usd", 0) or 0)
            return current_value
        return balance * price

    def _historical_yield_snapshot(self, position: Any, timestamp: int) -> dict:
        market_id = self._get(position, "market_id") or self._get(position, "pool_id")
        if not market_id:
            return {}
        snapshot = self.yield_snapshot_repository.get_latest_before(str(market_id), timestamp)
        return snapshot or {}

    def _save_cashflows(self, wallet: str, actions: list[dict]):
        rows = []
        for action in actions:
            price_at_tx = self.pricing.get_historical_price(
                action.get("symbol"),
                int(action.get("timestamp") or 0),
            )
            rows.append(
                {
                    "wallet": wallet,
                    "tx_id": action["tx_id"],
                    "timestamp": action["timestamp"],
                    "action": action["action"],
                    "action_label": self._action_label(action["action"]),
                    "event_source": "protocol",
                    "transaction_category": "protocol",
                    "direction": self._direction(action["action"]),
                    "market_id": action["market_id"],
                    "symbol": action["symbol"],
                    "amount": action["amount"],
                    "amount_usd": action["amount_usd"],
                    "recorded_amount_usd": action["amount_usd"],
                    "price_at_tx": price_at_tx,
                    "priceAtTx": price_at_tx,
                    "price_source": "historical_snapshot" if price_at_tx else "provider_recorded",
                }
            )
        self.cashflow_repository.bulk_upsert(rows)

    async def _sync_onchain_cashflows(self, wallet: str, start_block: int | None) -> int:
        try:
            crawler = OnchainTransactionCrawler()
        except ValueError as exc:
            self.logger.warning(f"Skip on-chain crawl: {exc}")
            return 0

        try:
            if start_block is None:
                latest_block = self.cashflow_repository.get_latest_onchain_block(wallet)
                start_block = latest_block + 1 if latest_block else 0

            rows, stats = await crawler.fetch_wallet_transactions(
                wallet=wallet,
                start_block=start_block,
            )
            cashflows = [self._onchain_row_to_cashflow(row) for row in rows]
            cashflows = [row for row in cashflows if row]
            self.cashflow_repository.bulk_upsert(cashflows)
            self.logger.info(
                "On-chain tx synced wallet=%s normal=%s erc20=%s saved=%s",
                wallet,
                stats["normal_tx_count"],
                stats["erc20_transfer_count"],
                len(cashflows),
            )
            return len(cashflows)
        except Exception as exc:
            self.logger.exception(f"On-chain crawl failed wallet={wallet}: {exc}")
            return 0
        finally:
            await crawler.close()

    def _onchain_row_to_cashflow(self, row: dict) -> dict | None:
        symbol = row.get("symbol")
        timestamp = int(row.get("timestamp") or 0)
        amount = float(row.get("amount") or 0)
        price_at_tx = self.pricing.get_historical_price(symbol, timestamp)
        amount_usd = amount * price_at_tx if price_at_tx else 0.0
        gas_cost_eth = float(row.get("gas_cost_eth") or 0.0)
        eth_price_at_tx = self.pricing.get_historical_price("ETH", timestamp)
        gas_cost_usd = gas_cost_eth * eth_price_at_tx if gas_cost_eth and eth_price_at_tx else 0.0
        tx_hash = row.get("tx_hash")
        log_index = row.get("log_index")
        direction = row.get("direction")

        if not tx_hash or not symbol or amount <= 0:
            return None

        return {
            "wallet": row["wallet"],
            "tx_id": f"{tx_hash}:{log_index}:{symbol}:{direction}",
            "tx_hash": tx_hash,
            "log_index": log_index,
            "block_number": row.get("block_number"),
            "timestamp": timestamp,
            "action": row["action"],
            "action_label": row.get("action_label") or self._action_label(row["action"]),
            "event_source": "onchain",
            "transaction_category": row.get("transaction_category") or self._category(row["action"]),
            "direction": direction,
            "market_id": row.get("to") or row.get("from") or "onchain",
            "symbol": symbol,
            "amount": amount,
            "amount_raw": row.get("amount_raw"),
            "amount_usd": round(amount_usd, 4),
            "recorded_amount_usd": 0.0,
            "price_at_tx": price_at_tx,
            "priceAtTx": price_at_tx,
            "price_source": "historical_snapshot" if price_at_tx else "missing_snapshot",
            "from": row.get("from"),
            "to": row.get("to"),
            "gas_cost_eth": gas_cost_eth,
            "gas_cost_usd": round(gas_cost_usd, 6),
            "protocol_fee_usd": 0.0,
            "contract_address": row.get("contract_address"),
            "asset_type": row.get("asset_type"),
            "source": "etherscan",
        }

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

    def _action_label(self, action: str) -> str:
        return {
            "deposit": "Deposit",
            "withdraw": "Withdraw",
            "borrow": "Borrow",
            "repay": "Repay",
            "buy": "Buy",
            "sell": "Sell",
            "transfer_in": "Receive",
            "transfer_out": "Send",
        }.get(action, action or "Unknown")

    def _direction(self, action: str) -> str | None:
        if action in ("deposit", "repay", "sell", "transfer_out"):
            return "out"
        if action in ("withdraw", "borrow", "buy", "transfer_in"):
            return "in"
        return None

    def _category(self, action: str) -> str:
        if action in ("buy", "sell"):
            return "swap"
        if action in ("transfer_in", "transfer_out"):
            return "transfer"
        return "protocol"

    def _get(self, item: Any, key: str, default=None):
        camel_key = self._snake_to_camel(key)
        if isinstance(item, dict):
            if key in item:
                return item.get(key, default)
            return item.get(camel_key, default)
        if hasattr(item, key):
            return getattr(item, key, default)
        return getattr(item, camel_key, default)

    def _snake_to_camel(self, key: str) -> str:
        if "_" not in key:
            return key
        parts = key.split("_")
        return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

    def _first(self, value):
        if isinstance(value, list):
            return value[0] if value else None
        return value
