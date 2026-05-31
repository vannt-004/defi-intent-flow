from datetime import datetime, timezone

from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.asset_snapshot_repository import AssetSnapshotRepository
from shared.repositories.cashflow_repository import CashflowRepository
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository


class PortfolioAnalyticsService:

    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)
        self.portfolio_repository = PortfolioRepository(self.db)
        self.asset_snapshot_repository = AssetSnapshotRepository(self.db)
        self.position_snapshot_repository = PositionSnapshotRepository(self.db)
        self.cashflow_repository = CashflowRepository(self.db)

    def get_dashboard(self, wallet: str) -> dict:
        wallet = wallet.lower()
        latest = self.portfolio_repository.get_latest_snapshot(wallet) or {}

        return {
            "netWorth": self._build_net_worth(latest),
            "pnlSummary": self._build_pnl_summary(wallet, latest),
            "positionsPnL": self.get_positions_pnl(wallet),
            "transactions": self.get_transactions(wallet, limit=20),
            "chartHistory": self.get_chart_history(wallet),
        }

    def get_transactions(self, wallet: str, limit: int = 100) -> list[dict]:
        wallet = wallet.lower()
        cashflows = self.cashflow_repository.get_wallet_cashflows_chronological(wallet)
        basis_by_symbol = {}
        amount_by_symbol = {}
        enriched = []

        for row in self._merge_events(cashflows):
            symbol = row.get("symbol")
            if not self._is_supported_symbol(symbol):
                continue

            action = row.get("action")
            amount = float(row.get("amount") or 0)
            estimated_price = float(row.get("price_at_tx") or row.get("priceAtTx") or 0) or self.pricing.get_historical_price(
                symbol,
                int(row.get("timestamp") or 0),
            )
            estimated_value = amount * estimated_price if estimated_price > 0 else float(row.get("amount_usd") or 0)
            realized_pnl = 0.0

            basis_by_symbol.setdefault(symbol, 0.0)
            amount_by_symbol.setdefault(symbol, 0.0)

            if action in ("deposit", "repay", "buy", "transfer_in"):
                basis_by_symbol[symbol] += estimated_value
                amount_by_symbol[symbol] += amount
            elif action in ("withdraw", "borrow", "sell", "transfer_out") and amount_by_symbol[symbol] > 0:
                consumed = min(amount, amount_by_symbol[symbol])
                avg_cost = basis_by_symbol[symbol] / amount_by_symbol[symbol]
                cost = avg_cost * consumed
                realized_pnl = estimated_value - cost if action in ("withdraw", "borrow", "sell") else 0.0
                basis_by_symbol[symbol] -= cost
                amount_by_symbol[symbol] -= consumed

            enriched.append(
                self._format_transaction(
                    row=row,
                    estimated_price=estimated_price,
                    estimated_value=estimated_value,
                    realized_pnl=realized_pnl,
                )
            )

        return list(reversed(enriched))[:limit]

    def get_positions_pnl(self, wallet: str) -> list[dict]:
        wallet = wallet.lower()
        assets = self.asset_snapshot_repository.get_latest_wallet_assets(wallet)
        positions = self.position_snapshot_repository.get_latest_wallet_positions(wallet)
        realized_by_symbol = self._calculate_realized_pnl_by_symbol(wallet)

        result = []
        for asset in assets:
            symbol = asset.get("symbol")
            current_price = float(asset.get("price") or 0)
            balance = float(asset.get("balance") or 0)
            value_usd = float(asset.get("value_usd") or 0)
            basis = self._calculate_symbol_cost_basis(wallet, symbol)
            pnl_usd = value_usd - basis + realized_by_symbol.get(symbol, 0.0)
            pnl_pct = (pnl_usd / basis * 100) if basis > 0 else None
            entry_price = (basis / balance) if balance > 0 and basis > 0 else None

            result.append({
                "positionId": f"hold-{symbol}",
                "name": symbol,
                "protocol": "Wallet",
                "type": "hold",
                "valueUsd": round(value_usd, 4),
                "balance": round(balance, 8),
                "costBasisUsd": round(basis, 4),
                "entryPrice": round(entry_price, 8) if entry_price else None,
                "currentPrice": round(current_price, 8) if current_price else None,
                "pnlUsd": round(pnl_usd, 4),
                "pnlPct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "pnlType": "unrealized",
                "healthFactor": 100,
                "apy": None,
            })

        for position in positions:
            side = position.get("side")
            symbol = position.get("symbol")
            value_usd = float(position.get("value_usd") or 0)
            balance = float(position.get("balance") or 0)
            pnl_usd = float(position.get("pnl_usd") or 0)
            pnl_pct = float(position.get("pnl_pct") or 0)
            is_amm = position.get("type") == "amm"
            position_type = "farm" if is_amm else ("borrow" if side == "BORROWER" else "lend")
            pnl_type = "yield" if is_amm else ("interest_cost" if side == "BORROWER" else "interest_earned")
            current_price = self._position_current_price(position, symbol, value_usd, balance)

            result.append({
                "positionId": position.get("position_id"),
                "name": symbol,
                "protocol": position.get("protocol"),
                "type": position_type,
                "valueUsd": -value_usd if side == "BORROWER" else value_usd,
                "balance": round(balance, 8),
                "costBasisUsd": round(float(position.get("previous_value_usd") or 0), 4),
                "entryPrice": None,
                "currentPrice": round(current_price, 8) if current_price else None,
                "pnlUsd": round(-abs(pnl_usd) if side == "BORROWER" else pnl_usd, 4),
                "pnlPct": round(pnl_pct, 4) if pnl_pct else None,
                "pnlType": pnl_type,
                "healthFactor": 100 if side != "BORROWER" else 50,
                "apy": float(position.get("borrow_apr") or 0) if side == "BORROWER" else float(position.get("supply_apr") or 0),
            })

        return result

    def _position_current_price(self, position: dict, symbol: str, value_usd: float, balance: float) -> float:
        if position.get("type") == "amm":
            return 0.0
        if balance > 0 and value_usd > 0:
            return value_usd / balance
        return self.pricing.get_price_safe(symbol, 0.0) if symbol else 0.0

    def get_chart_history(self, wallet: str, limit: int = 90) -> list[dict]:
        snapshots = self.portfolio_repository.get_snapshots_chronological(wallet.lower(), limit=limit)

        return [
            {
                "timestamp": row.get("timestamp"),
                "label": self._format_date(row.get("timestamp")),
                "tokenHold": round(float(row.get("token_hold_usd") or 0), 4),
                "positions": round(
                    float(row.get("total_supply_usd") or 0)
                    + float(row.get("total_amm_usd") or 0)
                    - float(row.get("total_borrow_usd") or 0),
                    4,
                ),
                "netWorth": round(float(row.get("net_worth_usd") or 0), 4),
            }
            for row in snapshots
        ]

    def _build_net_worth(self, latest: dict) -> dict:
        total_supply = float(latest.get("total_supply_usd") or 0)
        total_borrow = float(latest.get("total_borrow_usd") or 0)
        supply_interest = float(latest.get("supply_interest_usd") or 0)
        borrow_interest = float(latest.get("borrow_interest_usd") or 0)
        supply_principal = float(latest.get("supply_principal_usd") or max(total_supply - supply_interest, 0))
        borrow_principal = float(latest.get("borrow_principal_usd") or max(total_borrow - borrow_interest, 0))

        return {
            "totalUsd": round(float(latest.get("net_worth_usd") or 0), 4),
            "tokenHoldUsd": round(float(latest.get("token_hold_usd") or 0), 4),
            "lendingUsd": round(supply_principal, 4),
            "interestEarnedUsd": round(supply_interest, 4),
            "debtUsd": round(borrow_principal, 4),
            "debtInterestUsd": round(borrow_interest, 4),
            "farmingUsd": round(float(latest.get("total_amm_usd") or 0), 4),
        }

    def _build_pnl_summary(self, wallet: str, latest: dict) -> dict:
        current = float(latest.get("net_worth_usd") or 0)
        now = int(datetime.now(timezone.utc).timestamp())
        day = self.portfolio_repository.get_snapshot_at_or_before(wallet, now - 86400)
        week = self.portfolio_repository.get_snapshot_at_or_before(wallet, now - 86400 * 7)
        all_rows = self.portfolio_repository.get_snapshots_chronological(wallet, limit=1000)
        first = all_rows[0] if all_rows else None

        return {
            "todayUsd": self._delta(current, day),
            "todayPct": self._delta_pct(current, day),
            "sevenDayUsd": self._delta(current, week),
            "sevenDayPct": self._delta_pct(current, week),
            "allTimeUsd": self._delta(current, first),
            "allTimePct": self._delta_pct(current, first),
            "roiPct": self._delta_pct(current, first),
        }

    def _format_transaction(
        self,
        row: dict,
        estimated_price: float,
        estimated_value: float,
        realized_pnl: float,
    ) -> dict:
        symbol = row.get("symbol")
        timestamp = int(row.get("timestamp") or 0)
        amount = float(row.get("amount") or 0)
        amount_usd = float(row.get("amount_usd") or 0)
        action = row.get("action")
        tx_id = row.get("tx_id") or row.get("tx_hash")
        event_source = row.get("event_source") or row.get("source") or "protocol"
        category = row.get("transaction_category") or self._category(action, event_source)
        label = row.get("action_label") or self._action_label(action)
        tx_hash = row.get("tx_hash") or row.get("tx_id")
        direction = row.get("direction") or self._direction(action)
        log_index = row.get("log_index")
        unique_id = self._transaction_id(
            event_source=event_source,
            tx_id=tx_id,
            action=action,
            symbol=symbol,
            log_index=log_index,
        )

        return {
            "id": unique_id,
            "txId": tx_id,
            "txHash": tx_hash,
            "blockNumber": row.get("block_number"),
            "logIndex": log_index,
            "action": action,
            "actionLabel": label,
            "transactionCategory": category,
            "eventSource": event_source,
            "direction": direction,
            "description": self._describe_action(action, symbol),
            "symbol": symbol,
            "amount": amount,
            "amountUsd": round(estimated_value, 4),
            "recordedAmountUsd": round(amount_usd, 4),
            "priceAtTx": round(estimated_price, 8) if estimated_price else None,
            "estimatedExecutionPrice": round(estimated_price, 8) if estimated_price else None,
            "priceSource": row.get("price_source") or ("historical_snapshot" if estimated_price else "recorded_amount"),
            "realizedPnlUsd": round(realized_pnl, 4),
            "timestamp": timestamp,
            "type": self._transaction_type(action),
            "timeAgo": self._time_ago(timestamp),
            "source": self._source_label(row, event_source),
            "from": row.get("from"),
            "to": row.get("to"),
            "gasCostEth": round(float(row.get("gas_cost_eth") or 0), 10),
            "explorerUrl": f"https://etherscan.io/tx/{tx_hash}" if tx_hash else None,
        }

    def _calculate_symbol_cost_basis(self, wallet: str, symbol: str) -> float:
        basis = 0.0
        held_amount = 0.0

        for row in self._token_basis_events(wallet):
            if row.get("symbol") != symbol:
                continue

            action = row.get("action")
            amount = float(row.get("amount") or 0)
            value = self._estimated_value(row)

            if action in ("deposit", "repay", "buy", "transfer_in"):
                basis += value
                held_amount += amount
            elif action in ("withdraw", "borrow", "sell", "transfer_out") and held_amount > 0:
                avg_cost = basis / held_amount
                consumed = min(amount, held_amount)
                basis -= avg_cost * consumed
                held_amount -= consumed

        return max(basis, 0.0)

    def _calculate_realized_pnl_by_symbol(self, wallet: str) -> dict[str, float]:
        basis_by_symbol = {}
        amount_by_symbol = {}
        pnl_by_symbol = {}

        for row in self._token_basis_events(wallet):
            symbol = row.get("symbol")
            action = row.get("action")
            amount = float(row.get("amount") or 0)
            value = self._estimated_value(row)

            basis_by_symbol.setdefault(symbol, 0.0)
            amount_by_symbol.setdefault(symbol, 0.0)
            pnl_by_symbol.setdefault(symbol, 0.0)

            if action in ("deposit", "repay", "buy", "transfer_in"):
                basis_by_symbol[symbol] += value
                amount_by_symbol[symbol] += amount
            elif action in ("withdraw", "borrow", "sell") and amount_by_symbol[symbol] > 0:
                avg_cost = basis_by_symbol[symbol] / amount_by_symbol[symbol]
                cost = avg_cost * min(amount, amount_by_symbol[symbol])
                pnl_by_symbol[symbol] += value - cost
                basis_by_symbol[symbol] -= cost
                amount_by_symbol[symbol] -= min(amount, amount_by_symbol[symbol])
            elif action == "transfer_out" and amount_by_symbol[symbol] > 0:
                avg_cost = basis_by_symbol[symbol] / amount_by_symbol[symbol]
                cost = avg_cost * min(amount, amount_by_symbol[symbol])
                basis_by_symbol[symbol] -= cost
                amount_by_symbol[symbol] -= min(amount, amount_by_symbol[symbol])

        return pnl_by_symbol

    def _estimated_value(self, row: dict) -> float:
        price = float(row.get("price_at_tx") or row.get("priceAtTx") or 0) or self.pricing.get_historical_price(
            row.get("symbol"),
            int(row.get("timestamp") or 0),
        )
        amount = float(row.get("amount") or 0)
        if price > 0:
            return amount * price

        return float(row.get("amount_usd") or 0)

    def _token_basis_events(self, wallet: str) -> list[dict]:
        cashflows = self.cashflow_repository.get_wallet_cashflows_chronological(wallet)
        return self._merge_events(cashflows)

    def _merge_events(self, cashflows: list[dict]) -> list[dict]:
        events = []

        for row in cashflows:
            item = dict(row)
            item["event_source"] = item.get("event_source") or "protocol"
            item["transaction_category"] = item.get("transaction_category") or self._category(
                item.get("action"),
                item["event_source"],
            )
            item["action_label"] = item.get("action_label") or self._action_label(item.get("action"))
            events.append(item)

        events.sort(key=lambda item: (
            int(item.get("timestamp") or 0),
            str(item.get("tx_id") or item.get("tx_hash") or ""),
            int(item.get("log_index") or -1),
        ))
        return events

    def _is_supported_symbol(self, symbol: str | None) -> bool:
        if not symbol:
            return False

        try:
            self.pricing.get_token_info(symbol)
            return True
        except Exception:
            return False

    def _delta(self, current: float, previous: dict | None) -> float:
        if not previous:
            return 0.0

        return round(current - float(previous.get("net_worth_usd") or 0), 4)

    def _delta_pct(self, current: float, previous: dict | None) -> float:
        if not previous:
            return 0.0

        base = float(previous.get("net_worth_usd") or 0)
        return round((current - base) / base * 100, 4) if base > 0 else 0.0

    def _transaction_type(self, action: str) -> str:
        if action in ("withdraw", "borrow", "sell"):
            return "earn"
        if action in ("repay", "transfer_out"):
            return "cost"
        return "transfer"

    def _transaction_id(self, event_source: str, tx_id: str, action: str, symbol: str, log_index) -> str:
        suffix = log_index if log_index is not None else "cashflow"
        return f"{event_source}:{tx_id}:{suffix}:{action}:{symbol}"

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

    def _category(self, action: str, event_source: str) -> str:
        if event_source == "protocol":
            return "protocol"
        if action in ("buy", "sell"):
            return "swap"
        if action in ("transfer_in", "transfer_out"):
            return "transfer"

        return "onchain"

    def _direction(self, action: str) -> str | None:
        if action in ("deposit", "repay", "sell", "transfer_out"):
            return "out"
        if action in ("withdraw", "borrow", "buy", "transfer_in"):
            return "in"

        return None

    def _source_label(self, row: dict, event_source: str) -> str:
        if event_source == "protocol":
            return row.get("market_id") or "protocol"

        category = row.get("transaction_category")
        if category == "swap":
            return "on-chain swap"
        if category == "transfer":
            return "on-chain transfer"

        return "on-chain"

    def _describe_action(self, action: str, symbol: str) -> str:
        return f"{self._action_label(action)} {symbol}"

    def _format_date(self, timestamp: int | None) -> str:
        if not timestamp:
            return ""

        return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%m-%d")

    def _time_ago(self, timestamp: int) -> str:
        if not timestamp:
            return ""

        seconds = max(int(datetime.now(timezone.utc).timestamp()) - timestamp, 0)
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"

        return f"{seconds // 86400}d ago"
