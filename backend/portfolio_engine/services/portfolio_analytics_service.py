from datetime import datetime, timezone
import re

from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.asset_snapshot_repository import AssetSnapshotRepository
from shared.repositories.cashflow_repository import CashflowRepository
from shared.repositories.portfolio_dashboard_view_repository import PortfolioDashboardViewRepository
from shared.repositories.portfolio_repository import PortfolioRepository
from shared.repositories.position_snapshot_repository import PositionSnapshotRepository


class PortfolioAnalyticsService:
    TOKEN_HOLD_INFLOW_ACTIONS = {"buy"}
    TOKEN_HOLD_OUTFLOW_ACTIONS = {"sell", "transfer_out", "deposit", "repay"}
    TOKEN_HOLD_REALIZED_ACTIONS = {"sell"}
    TOKEN_HOLD_UNKNOWN_COST_ACTIONS = {"transfer_in", "withdraw", "borrow"}
    MIN_DISPLAY_VALUE_USD = 0.01

    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)
        self.portfolio_repository = PortfolioRepository(self.db)
        self.dashboard_view_repository = PortfolioDashboardViewRepository(self.db)
        self.asset_snapshot_repository = AssetSnapshotRepository(self.db)
        self.position_snapshot_repository = PositionSnapshotRepository(self.db)
        self.cashflow_repository = CashflowRepository(self.db)

    def get_dashboard(self, wallet: str) -> dict:
        wallet = wallet.lower()
        latest = self.portfolio_repository.get_latest_snapshot(wallet) or {}
        cached = self.dashboard_view_repository.get_view_row(wallet)
        if (
            cached
            and cached.get("payload")
            and cached.get("sourceTimestamp") == latest.get("timestamp")
            and cached.get("schemaVersion") == self.dashboard_view_repository.SCHEMA_VERSION
        ):
            return cached["payload"]

        return self.refresh_dashboard_view(wallet)

    def refresh_dashboard_view(self, wallet: str) -> dict:
        wallet = wallet.lower()
        latest = self.portfolio_repository.get_latest_snapshot(wallet) or {}
        cached = self.dashboard_view_repository.get_view_row(wallet)
        cashflow_watermark = self.cashflow_repository.get_wallet_watermark(wallet)
        refresh_mode = "full"

        if self._can_reuse_cashflow_sections(cached, cashflow_watermark):
            payload = self._build_dashboard_from_cached_cashflows(wallet, cached["payload"], latest)
            refresh_mode = "incremental_snapshot"
        else:
            payload = self._build_dashboard(wallet)

        self.dashboard_view_repository.upsert_view(
            wallet=wallet,
            payload=payload,
            source_timestamp=latest.get("timestamp"),
            metadata={
                "cashflowWatermark": cashflow_watermark,
                "refreshMode": refresh_mode,
                "refreshedAt": int(datetime.now(timezone.utc).timestamp()),
            },
        )
        return payload

    def _build_dashboard(self, wallet: str) -> dict:
        latest = self.portfolio_repository.get_latest_snapshot(wallet) or {}
        enriched_transactions = self._build_enriched_transactions(wallet)
        pnl_flows = self.get_pnl_flows(wallet, enriched_transactions=enriched_transactions)

        return {
            "netWorth": self._build_net_worth(latest),
            "pnlSummary": self._build_pnl_summary(wallet, latest),
            "positionsPnL": self.get_positions_pnl(wallet, pnl_flows=pnl_flows),
            "transactions": self.get_transactions(wallet, limit=20, enriched_transactions=enriched_transactions),
            "transactionPoolGroups": self.get_transaction_pool_groups(wallet, enriched_transactions=enriched_transactions),
            "pnlFlows": pnl_flows,
            "chartHistory": self.get_chart_history(wallet),
            "readModel": {
                "refreshMode": "full",
                "cashflowIncremental": False,
            },
        }

    def _build_dashboard_from_cached_cashflows(self, wallet: str, cached_payload: dict, latest: dict) -> dict:
        cached_payload = cached_payload or {}
        cached_transactions = cached_payload.get("transactions")
        cached_pool_groups = cached_payload.get("transactionPoolGroups")
        cached_pnl_flows = cached_payload.get("pnlFlows")
        pnl_flows = self._refresh_cached_pnl_flows(wallet, cached_pnl_flows or [])

        return {
            "netWorth": self._build_net_worth(latest),
            "pnlSummary": self._build_pnl_summary(wallet, latest),
            "positionsPnL": self.get_positions_pnl(wallet, pnl_flows=pnl_flows),
            "transactions": cached_transactions or self.get_transactions(wallet, limit=20),
            "transactionPoolGroups": cached_pool_groups or self.get_transaction_pool_groups(wallet),
            "pnlFlows": pnl_flows,
            "chartHistory": self.get_chart_history(wallet),
            "readModel": {
                "refreshMode": "incremental_snapshot",
                "cashflowIncremental": True,
            },
        }

    def _can_reuse_cashflow_sections(self, cached: dict | None, cashflow_watermark: dict) -> bool:
        if not cached or cached.get("schemaVersion") != self.dashboard_view_repository.SCHEMA_VERSION:
            return False
        metadata = cached.get("metadata") or {}
        cached_payload = cached.get("payload") or {}
        return (
            bool(cached_payload)
            and metadata.get("cashflowWatermark") == cashflow_watermark
        )

    def get_transactions(
        self,
        wallet: str,
        limit: int = 100,
        enriched_transactions: list[dict] | None = None,
    ) -> list[dict]:
        transactions = enriched_transactions if enriched_transactions is not None else self._build_enriched_transactions(wallet)
        return list(reversed(transactions))[:limit]

    def get_transaction_pool_groups(
        self,
        wallet: str,
        limit: int = 12,
        enriched_transactions: list[dict] | None = None,
    ) -> list[dict]:
        transactions = enriched_transactions if enriched_transactions is not None else self._build_enriched_transactions(wallet)
        groups: dict[str, dict] = {}

        for tx in transactions:
            if not self._is_protocol_pool_transaction(tx):
                continue

            pool_key = tx.get("marketId") or tx.get("poolId") or tx.get("poolKey")
            group = groups.setdefault(pool_key, {
                "poolKey": pool_key,
                "poolLabel": tx.get("poolLabel") or tx.get("source") or "Protocol pool",
                "protocol": tx.get("protocol") or tx.get("eventSource") or "protocol",
                "symbols": set(),
                "transactionCount": 0,
                "inflowUsd": 0.0,
                "outflowUsd": 0.0,
                "netFlowUsd": 0.0,
                "realizedPnlUsd": 0.0,
                "gasUsd": 0.0,
                "lastTimestamp": 0,
                "actions": {},
            })
            symbol = tx.get("symbol")
            if symbol:
                group["symbols"].add(symbol)

            amount_usd = abs(float(tx.get("amountUsd") or 0))
            if tx.get("direction") == "in":
                group["inflowUsd"] += amount_usd
                group["netFlowUsd"] += amount_usd
            elif tx.get("direction") == "out":
                group["outflowUsd"] += amount_usd
                group["netFlowUsd"] -= amount_usd

            action = tx.get("action") or "unknown"
            group["actions"][action] = group["actions"].get(action, 0) + 1
            group["transactionCount"] += 1
            group["realizedPnlUsd"] += float(tx.get("realizedPnlUsd") or 0)
            group["gasUsd"] += float(tx.get("gasCostUsd") or 0)
            group["lastTimestamp"] = max(int(group["lastTimestamp"] or 0), int(tx.get("timestamp") or 0))

        rows = []
        for group in groups.values():
            realized_pnl = group["realizedPnlUsd"]
            if realized_pnl > 0:
                status = "take_profit"
            elif realized_pnl < 0:
                status = "loss"
            else:
                status = "neutral"

            rows.append({
                "poolKey": group["poolKey"],
                "poolLabel": group["poolLabel"],
                "protocol": group["protocol"],
                "symbols": sorted(group["symbols"]),
                "transactionCount": group["transactionCount"],
                "inflowUsd": round(group["inflowUsd"], 4),
                "outflowUsd": round(group["outflowUsd"], 4),
                "netFlowUsd": round(group["netFlowUsd"], 4),
                "realizedPnlUsd": round(realized_pnl, 4),
                "gasUsd": round(group["gasUsd"], 4),
                "lastTimestamp": group["lastTimestamp"],
                "status": status,
                "actions": group["actions"],
            })

        rows.sort(key=lambda item: (abs(item["realizedPnlUsd"]), item["lastTimestamp"]), reverse=True)
        return rows[:limit]

    def _is_protocol_pool_transaction(self, tx: dict) -> bool:
        category = tx.get("transactionCategory")
        event_source = tx.get("eventSource")
        protocol = str(tx.get("protocol") or "").lower()
        if event_source == "onchain" or category in ("transfer", "swap", "onchain") or protocol in ("onchain", "etherscan"):
            return False
        has_protocol_ref = bool(tx.get("marketId") or tx.get("poolId"))
        return category == "protocol" or event_source == "protocol" or has_protocol_ref

    def get_pnl_flows(
        self,
        wallet: str,
        limit: int = 30,
        enriched_transactions: list[dict] | None = None,
    ) -> list[dict]:
        wallet = wallet.lower()
        all_transactions = enriched_transactions if enriched_transactions is not None else self._build_enriched_transactions(wallet)
        gas_by_hash = self._gas_by_tx_hash(all_transactions)
        transactions = [tx for tx in all_transactions if self._is_protocol_pool_transaction(tx)]
        positions = self.position_snapshot_repository.get_latest_wallet_positions(wallet)
        position_by_key = {}

        for position in positions:
            for key in self._position_flow_keys(position):
                if key and key not in position_by_key:
                    position_by_key[key] = position

        groups: dict[str, dict] = {}

        for position in positions:
            flow_key = self._position_flow_key(position)
            if not flow_key:
                continue
            groups.setdefault(flow_key, self._new_pnl_flow_group(flow_key, position=position))

        for tx in transactions:
            flow_key = tx.get("marketId") or tx.get("poolId") or tx.get("poolKey")
            if not flow_key:
                continue
            position = position_by_key.get(flow_key)
            group = groups.setdefault(flow_key, self._new_pnl_flow_group(flow_key, position=position, tx=tx))
            self._apply_tx_to_pnl_flow(group, tx, gas_by_hash)

        rows = []
        for group in groups.values():
            current_value = float(group["currentValueUsd"] or 0)
            status = "open" if current_value > 0 else ("closed" if group["transactionCount"] > 0 else "snapshot_only")
            position_type = "borrow" if group.get("type") == "borrow" else ("farm" if group.get("type") == "lp" else "lend")
            pnl_metrics = self._protocol_pnl_metrics(position_type, group)

            rows.append({
                "flowKey": group["flowKey"],
                "positionId": group.get("positionId"),
                "marketId": group.get("marketId"),
                "poolId": group.get("poolId"),
                "protocol": group["protocol"],
                "label": group["label"],
                "type": group["type"],
                "side": group.get("side"),
                "symbols": sorted(group["symbols"]),
                "currentValueUsd": round(current_value, 4),
                "inflowUsd": round(float(group["inflowUsd"]), 4),
                "outflowUsd": round(float(group["outflowUsd"]), 4),
                "netCashflowUsd": round(float(group["inflowUsd"]) - float(group["outflowUsd"]), 4),
                "gasUsd": round(float(group["gasUsd"]), 4),
                "estimatedPnlUsd": round(float(pnl_metrics["pnlUsd"]), 4),
                "estimatedPnlPct": round(float(pnl_metrics["pnlPct"]), 4) if pnl_metrics["pnlPct"] is not None else None,
                "pnlReliable": bool(pnl_metrics["reliable"]),
                "pnlNote": pnl_metrics["note"],
                "transactionCount": group["transactionCount"],
                "firstTimestamp": group["firstTimestamp"] or None,
                "lastTimestamp": group["lastTimestamp"] or None,
                "status": status,
                "marketLinkSymbol": self._market_link_symbol(group),
                "events": sorted(group["events"], key=lambda item: item["timestamp"], reverse=True),
                "formula": pnl_metrics["formula"],
                "capitalBaseUsd": round(float(pnl_metrics["capitalBaseUsd"]), 4),
                "actions": group.get("actions") or {},
            })

        rows.sort(key=lambda item: (item["currentValueUsd"], item["lastTimestamp"] or 0), reverse=True)
        return rows[:limit]

    def _refresh_cached_pnl_flows(self, wallet: str, cached_flows: list[dict], limit: int = 30) -> list[dict]:
        if not cached_flows:
            return self.get_pnl_flows(wallet, limit=limit)

        positions = self.position_snapshot_repository.get_latest_wallet_positions(wallet.lower())
        position_by_key = {}
        for position in positions:
            for key in self._position_flow_keys(position):
                if key and key not in position_by_key:
                    position_by_key[key] = position

        rows = []
        seen_keys = set()
        for flow in cached_flows:
            row = dict(flow)
            flow_key = row.get("flowKey")
            seen_keys.add(flow_key)
            position = position_by_key.get(flow_key)
            current_value = abs(float(position.get("value_usd") or 0)) if position else float(row.get("currentValueUsd") or 0)
            row["currentValueUsd"] = round(current_value, 4)
            position_type = "borrow" if row.get("type") == "borrow" else ("farm" if row.get("type") == "lp" else "lend")
            pnl_metrics = self._protocol_pnl_metrics(position_type, row)
            row["estimatedPnlUsd"] = round(float(pnl_metrics["pnlUsd"]), 4)
            row["estimatedPnlPct"] = round(float(pnl_metrics["pnlPct"]), 4) if pnl_metrics["pnlPct"] is not None else None
            row["pnlReliable"] = bool(pnl_metrics["reliable"])
            row["pnlNote"] = pnl_metrics["note"]
            row["status"] = "open" if current_value > 0 else ("closed" if row.get("transactionCount") else "snapshot_only")
            row["formula"] = pnl_metrics["formula"]
            row["capitalBaseUsd"] = round(float(pnl_metrics["capitalBaseUsd"]), 4)
            rows.append(row)

        for position in positions:
            flow_key = self._position_flow_key(position)
            if flow_key and flow_key not in seen_keys:
                group = self._new_pnl_flow_group(flow_key, position=position)
                pnl_metrics = self._protocol_pnl_metrics(
                    "farm" if group["type"] == "lp" else ("borrow" if group["type"] == "borrow" else "lend"),
                    group,
                )
                rows.append({
                    "flowKey": group["flowKey"],
                    "positionId": group.get("positionId"),
                    "marketId": group.get("marketId"),
                    "poolId": group.get("poolId"),
                    "protocol": group["protocol"],
                    "label": group["label"],
                    "type": group["type"],
                    "side": group.get("side"),
                    "symbols": sorted(group["symbols"]),
                    "currentValueUsd": round(float(group["currentValueUsd"] or 0), 4),
                    "inflowUsd": 0.0,
                    "outflowUsd": 0.0,
                    "netCashflowUsd": 0.0,
                    "gasUsd": 0.0,
                    "estimatedPnlUsd": round(float(pnl_metrics["pnlUsd"]), 4),
                    "estimatedPnlPct": round(float(pnl_metrics["pnlPct"]), 4) if pnl_metrics["pnlPct"] is not None else None,
                    "pnlReliable": bool(pnl_metrics["reliable"]),
                    "pnlNote": pnl_metrics["note"],
                    "transactionCount": 0,
                    "firstTimestamp": None,
                    "lastTimestamp": None,
                    "status": "open" if float(group["currentValueUsd"] or 0) > 0 else "snapshot_only",
                    "marketLinkSymbol": self._market_link_symbol(group),
                    "events": [],
                    "formula": pnl_metrics["formula"],
                    "capitalBaseUsd": round(float(pnl_metrics["capitalBaseUsd"]), 4),
                    "actions": group.get("actions") or {},
                })

        rows.sort(key=lambda item: (float(item.get("currentValueUsd") or 0), item.get("lastTimestamp") or 0), reverse=True)
        return rows[:limit]

    def _gas_by_tx_hash(self, transactions: list[dict]) -> dict[str, float]:
        gas_by_hash = {}
        for tx in transactions:
            tx_hash = (tx.get("txHash") or tx.get("txId") or "").lower()
            gas = float(tx.get("gasCostUsd") or 0)
            if tx_hash and gas > 0:
                gas_by_hash[tx_hash] = max(gas_by_hash.get(tx_hash, 0.0), gas)
        return gas_by_hash

    def _position_flow_keys(self, position: dict) -> list[str]:
        return [
            position.get("market_id"),
            position.get("pool_id"),
            position.get("position_id"),
        ]

    def _position_flow_key(self, position: dict) -> str | None:
        for key in self._position_flow_keys(position):
            if key:
                return key
        return None

    def _new_pnl_flow_group(self, flow_key: str, position: dict | None = None, tx: dict | None = None) -> dict:
        position = position or {}
        tx = tx or {}
        symbols = set()
        for symbol in [position.get("symbol"), tx.get("symbol"), position.get("token0"), position.get("token1")]:
            if symbol:
                symbols.add(symbol)

        protocol = position.get("protocol") or tx.get("protocol") or "protocol"
        label = (
            position.get("symbol")
            or tx.get("poolLabel")
            or tx.get("source")
            or "Protocol position"
        )

        return {
            "flowKey": flow_key,
            "positionId": position.get("position_id"),
            "marketId": position.get("market_id") or tx.get("marketId"),
            "poolId": position.get("pool_id") or tx.get("poolId"),
            "protocol": protocol,
            "label": label,
            "type": "lp" if position.get("type") == "amm" else ("borrow" if position.get("side") == "BORROWER" else "lending"),
            "side": position.get("side"),
            "symbols": symbols,
            "currentValueUsd": abs(float(position.get("value_usd") or 0)),
            "inflowUsd": 0.0,
            "outflowUsd": 0.0,
            "gasUsd": 0.0,
            "transactionCount": 0,
            "firstTimestamp": 0,
            "lastTimestamp": 0,
            "events": [],
            "actions": {},
        }

    def _flow_pnl_usd(self, group: dict, current_value: float | None = None) -> float:
        current_value = float(group.get("currentValueUsd") if current_value is None else current_value)
        inflow = float(group.get("inflowUsd") or 0)
        outflow = float(group.get("outflowUsd") or 0)
        gas = float(group.get("gasUsd") or 0)
        if group.get("side") == "BORROWER" or group.get("type") == "borrow":
            return inflow - outflow - current_value - gas
        return current_value + inflow - outflow - gas

    def _flow_formula(self, group: dict) -> str:
        if group.get("side") == "BORROWER" or group.get("type") == "borrow":
            return "borrowed received - repays supplied - current debt - gas"
        return "current value + withdrawals/rewards received - deposits supplied - gas"

    def _apply_tx_to_pnl_flow(self, group: dict, tx: dict, gas_by_hash: dict[str, float] | None = None):
        symbol = tx.get("symbol")
        if symbol:
            group["symbols"].add(symbol)
        if tx.get("marketId") and not group.get("marketId"):
            group["marketId"] = tx.get("marketId")
        if tx.get("poolId") and not group.get("poolId"):
            group["poolId"] = tx.get("poolId")

        value = self._flow_event_value_usd(tx)
        if tx.get("direction") == "in":
            group["inflowUsd"] += value
        elif tx.get("direction") == "out":
            group["outflowUsd"] += value

        tx_hash = (tx.get("txHash") or tx.get("txId") or "").lower()
        gas = float(tx.get("gasCostUsd") or 0)
        if gas <= 0 and gas_by_hash and tx_hash:
            gas = float(gas_by_hash.get(tx_hash) or 0)
        group["gasUsd"] += gas
        timestamp = int(tx.get("timestamp") or 0)
        action = tx.get("action") or "unknown"
        group["actions"][action] = int(group["actions"].get(action) or 0) + 1
        group["transactionCount"] += 1
        group["firstTimestamp"] = timestamp if not group["firstTimestamp"] else min(group["firstTimestamp"], timestamp)
        group["lastTimestamp"] = max(group["lastTimestamp"], timestamp)
        group["events"].append({
            "id": tx.get("id"),
            "txId": tx.get("txId"),
            "txHash": tx_hash or tx.get("txHash"),
            "timestamp": timestamp,
            "timeAgo": tx.get("timeAgo"),
            "action": tx.get("action"),
            "actionLabel": tx.get("actionLabel") or self._action_label(tx.get("action")),
            "direction": tx.get("direction"),
            "symbol": symbol,
            "amount": tx.get("amount"),
            "amountUsd": tx.get("amountUsd"),
            "recordedAmountUsd": tx.get("recordedAmountUsd"),
            "priceAtTx": tx.get("priceAtTx"),
            "priceSource": tx.get("priceSource"),
            "priceTimestamp": tx.get("priceTimestamp"),
            "priceDeltaSeconds": tx.get("priceDeltaSeconds"),
            "priceMaxDeltaSeconds": tx.get("priceMaxDeltaSeconds"),
            "priceReliable": tx.get("priceReliable"),
            "priceNote": tx.get("priceNote"),
            "gasCostUsd": gas,
            "explorerUrl": tx.get("explorerUrl"),
            "description": self._pnl_flow_event_description(tx),
        })

    def _flow_event_value_usd(self, tx: dict) -> float:
        recorded = abs(float(tx.get("recordedAmountUsd") or 0))
        estimated = abs(float(tx.get("amountUsd") or 0))
        if tx.get("eventSource") == "protocol" and recorded > 0:
            return recorded
        return estimated or recorded

    def _protocol_pnl_metrics(self, position_type: str, flow: dict | None) -> dict:
        if not flow or int(flow.get("transactionCount") or 0) <= 0:
            return self._unreliable_protocol_pnl(
                note="PnL unavailable: no protocol cashflow in the tracked window",
                formula=self._flow_formula(flow or {"type": position_type}),
            )

        metric_flow = dict(flow)
        if position_type == "borrow":
            metric_flow["type"] = "borrow"
            metric_flow["side"] = metric_flow.get("side") or "BORROWER"
        current_value = float(metric_flow.get("currentValueUsd") or 0)
        inflow = float(metric_flow.get("inflowUsd") or 0)
        outflow = float(metric_flow.get("outflowUsd") or 0)
        gas = float(metric_flow.get("gasUsd") or 0)
        actions = metric_flow.get("actions") or {}

        if position_type == "farm":
            return self._unreliable_protocol_pnl(
                note="LP PnL unavailable: fee/yield and liquidity-range attribution is not reliable enough yet",
                formula="current LP value + withdrawals/fees - deposits - gas",
            )

        if position_type == "borrow":
            if not actions.get("borrow") and inflow <= 0:
                return self._unreliable_protocol_pnl(
                    note="Borrow cost unavailable: no borrow cashflow in the tracked window",
                    formula=self._flow_formula(flow),
                )
            pnl_usd = self._flow_pnl_usd(metric_flow, current_value)
            capital_base = inflow
            note = "Flow-based borrow cost: borrowed received - repaid - current debt - gas. Token cost basis is not required."
        else:
            if not actions.get("deposit") and outflow <= 0:
                return self._unreliable_protocol_pnl(
                    note="Lending PnL unavailable: no supply/deposit cashflow in the tracked window",
                    formula=self._flow_formula(metric_flow),
                )
            pnl_usd = self._flow_pnl_usd(metric_flow, current_value)
            capital_base = outflow
            note = "Flow-based lending PnL: current supplied value + withdrawals - deposits - gas. Token cost basis is not required."

        sanity_note = self._protocol_flow_sanity_note(
            current_value=current_value,
            inflow=inflow,
            outflow=outflow,
            pnl_usd=pnl_usd,
        )
        if sanity_note:
            return self._unreliable_protocol_pnl(
                note=sanity_note,
                formula=self._flow_formula(metric_flow),
                capital_base=capital_base,
            )

        pnl_pct = (pnl_usd / capital_base * 100) if capital_base > 0 else None
        return {
            "pnlUsd": pnl_usd,
            "pnlPct": pnl_pct,
            "reliable": True,
            "note": note,
            "formula": self._flow_formula(metric_flow),
            "capitalBaseUsd": capital_base,
        }

    def _unreliable_protocol_pnl(self, note: str, formula: str, capital_base: float = 0.0) -> dict:
        return {
            "pnlUsd": 0.0,
            "pnlPct": None,
            "reliable": False,
            "note": note,
            "formula": formula,
            "capitalBaseUsd": capital_base,
        }

    def _protocol_flow_sanity_note(self, current_value: float, inflow: float, outflow: float, pnl_usd: float) -> str | None:
        largest_flow = max(abs(inflow), abs(outflow))
        if current_value > 0 and largest_flow > max(current_value * 100, 10_000_000):
            return "PnL unavailable: protocol cashflow value is out of range versus the current position, likely incomplete history or provider decimal mismatch"
        gross = current_value + abs(inflow) + abs(outflow)
        if gross > 0 and abs(pnl_usd) > gross + max(gross * 0.05, 1.0):
            return "PnL unavailable: flow result failed sanity checks"
        return None

    def _market_link_symbol(self, group: dict) -> str:
        symbols = sorted(group.get("symbols") or [])
        return symbols[0] if symbols else ""

    def _pnl_flow_event_description(self, tx: dict) -> str:
        action = tx.get("actionLabel") or self._action_label(tx.get("action"))
        amount = float(tx.get("amount") or 0)
        symbol = tx.get("symbol") or ""
        price = tx.get("priceAtTx")
        value = tx.get("amountUsd")
        price_text = f" @ {self._format_usd(price)}" if price else ""
        value_text = f" · {self._format_usd(value)}" if value is not None else ""
        return f"{action} {self._format_token_amount(amount)} {symbol}{price_text}{value_text}".strip()

    def _format_token_amount(self, value: float) -> str:
        text = f"{value:,.6f}".rstrip("0").rstrip(".")
        return text or "0"

    def _format_usd(self, value: float) -> str:
        if abs(value) >= 1:
            return f"${value:,.2f}"
        return f"${value:,.6f}".rstrip("0").rstrip(".")

    def _build_enriched_transactions(self, wallet: str) -> list[dict]:
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
            price_quote = self._price_quote_for_row(row)
            estimated_price = float(price_quote.get("price") or 0)
            estimated_value = amount * estimated_price if estimated_price > 0 else float(row.get("amount_usd") or 0)
            realized_pnl = 0.0

            basis_by_symbol.setdefault(symbol, 0.0)
            amount_by_symbol.setdefault(symbol, 0.0)

            if not row.get("exclude_from_token_basis"):
                realized_pnl = self._apply_token_hold_basis_event(
                    symbol=symbol,
                    action=action,
                    amount=amount,
                    value=estimated_value,
                    basis_by_symbol=basis_by_symbol,
                    amount_by_symbol=amount_by_symbol,
                )

            enriched.append(
                self._format_transaction(
                    row=row,
                    estimated_price=estimated_price,
                    estimated_value=estimated_value,
                    realized_pnl=realized_pnl,
                    price_quote=price_quote,
                )
            )

        return enriched

    def get_positions_pnl(self, wallet: str, pnl_flows: list[dict] | None = None) -> list[dict]:
        wallet = wallet.lower()
        assets = self.asset_snapshot_repository.get_latest_wallet_assets(wallet)
        positions = self.position_snapshot_repository.get_latest_wallet_positions(wallet)
        basis_by_symbol, realized_by_symbol, basis_meta_by_symbol = self._calculate_basis_and_realized_by_symbol(wallet)
        flow_by_key = self._pnl_flow_by_position_key(pnl_flows or self.get_pnl_flows(wallet, limit=100))

        result = []
        for asset in assets:
            symbol = asset.get("symbol")
            current_price = float(asset.get("price") or 0)
            balance = float(asset.get("balance") or 0)
            value_usd = float(asset.get("value_usd") or 0)
            if value_usd < self.MIN_DISPLAY_VALUE_USD:
                continue
            basis = basis_by_symbol.get(symbol, 0.0)
            realized_pnl = realized_by_symbol.get(symbol, 0.0)
            basis_meta = basis_meta_by_symbol.get(symbol, {})
            pnl_reliable = bool(basis_meta.get("reliable"))
            pnl_usd = value_usd - basis + realized_pnl if pnl_reliable else 0.0
            pnl_pct = (pnl_usd / basis * 100) if pnl_reliable and basis > 0 else None
            entry_price = (basis / balance) if balance > 0 and basis > 0 else None
            basis_note = basis_meta.get("note") or "Token PnL unavailable: verified cost basis is missing"

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
                "pnlReliable": pnl_reliable,
                "pnlNote": basis_note,
                "pnlMethod": "average_cost_basis" if pnl_reliable else "basis_unavailable",
                "costBasisReliable": pnl_reliable,
                "healthFactor": 100,
                "apy": None,
            })

        for position in positions:
            side = position.get("side")
            symbol = position.get("symbol")
            value_usd = float(position.get("value_usd") or 0)
            if abs(value_usd) < self.MIN_DISPLAY_VALUE_USD:
                continue
            pnl_usd = 0.0
            pnl_pct = None
            flow = self._flow_for_position(position, flow_by_key)
            is_amm = position.get("type") == "amm"
            balance = None if is_amm else float(position.get("balance") or 0)
            position_type = "farm" if is_amm else ("borrow" if side == "BORROWER" else "lend")
            pnl_type = "yield" if is_amm else ("interest_cost" if side == "BORROWER" else "interest_earned")
            display_name = self._position_display_name(position, symbol)
            current_price = self._position_current_price(position, symbol, value_usd, balance or 0)
            pnl_metrics = self._protocol_pnl_metrics(position_type, flow)
            pnl_usd = float(pnl_metrics["pnlUsd"])
            pnl_pct = pnl_metrics["pnlPct"]
            capital_base = float(pnl_metrics["capitalBaseUsd"] or 0)
            pnl_reliable = bool(pnl_metrics["reliable"])

            result.append({
                "positionId": position.get("position_id"),
                "name": display_name,
                "protocol": position.get("protocol"),
                "type": position_type,
                "valueUsd": -value_usd if side == "BORROWER" else value_usd,
                "balance": round(balance, 8) if balance is not None else None,
                "token0": self._position_token(position, 0),
                "token1": self._position_token(position, 1),
                "amount0": position.get("amount0"),
                "amount1": position.get("amount1"),
                "costBasisUsd": round(capital_base, 4),
                "entryPrice": None,
                "currentPrice": round(current_price, 8) if current_price else None,
                "pnlUsd": round(pnl_usd, 4),
                "pnlPct": round(pnl_pct, 4) if pnl_pct is not None else None,
                "pnlType": pnl_type,
                "pnlReliable": pnl_reliable,
                "pnlNote": pnl_metrics["note"],
                "pnlMethod": "protocol_cashflow" if pnl_reliable else "flow_unavailable",
                "costBasisReliable": pnl_reliable and capital_base > 0,
                "healthFactor": 100 if side != "BORROWER" else 50,
                "apy": float(position.get("borrow_apr") or 0) if side == "BORROWER" else float(position.get("supply_apr") or 0),
            })

        return result

    def _pnl_flow_by_position_key(self, pnl_flows: list[dict]) -> dict[str, dict]:
        by_key = {}
        for flow in pnl_flows:
            for key in [flow.get("flowKey"), flow.get("positionId"), flow.get("marketId"), flow.get("poolId")]:
                if key and key not in by_key:
                    by_key[key] = flow
        return by_key

    def _flow_for_position(self, position: dict, flow_by_key: dict[str, dict]) -> dict | None:
        for key in self._position_flow_keys(position):
            if key and key in flow_by_key:
                return flow_by_key[key]
        return None

    def _position_display_name(self, position: dict, fallback_symbol: str | None) -> str:
        if position.get("type") == "amm":
            assets = position.get("asset") or []
            symbols = [str(symbol) for symbol in assets if symbol]
            if len(symbols) >= 2:
                return "/".join(symbols[:2])
        return fallback_symbol or "UNKNOWN"

    def _position_token(self, position: dict, index: int) -> str | None:
        assets = position.get("asset") or []
        return assets[index] if len(assets) > index else None

    def _apply_token_hold_basis_event(
        self,
        symbol: str,
        action: str,
        amount: float,
        value: float,
        basis_by_symbol: dict[str, float],
        amount_by_symbol: dict[str, float],
        pnl_by_symbol: dict[str, float] | None = None,
    ) -> float:
        if not symbol or amount <= 0:
            return 0.0

        basis_by_symbol.setdefault(symbol, 0.0)
        amount_by_symbol.setdefault(symbol, 0.0)
        if pnl_by_symbol is not None:
            pnl_by_symbol.setdefault(symbol, 0.0)

        if action in self.TOKEN_HOLD_INFLOW_ACTIONS:
            basis_by_symbol[symbol] += max(value, 0.0)
            amount_by_symbol[symbol] += amount
            return 0.0

        if action not in self.TOKEN_HOLD_OUTFLOW_ACTIONS or amount_by_symbol[symbol] <= 0:
            return 0.0

        consumed = min(amount, amount_by_symbol[symbol])
        if consumed <= 0:
            return 0.0

        avg_cost = basis_by_symbol[symbol] / amount_by_symbol[symbol] if amount_by_symbol[symbol] > 0 else 0.0
        cost = avg_cost * consumed
        basis_by_symbol[symbol] = max(basis_by_symbol[symbol] - cost, 0.0)
        amount_by_symbol[symbol] = max(amount_by_symbol[symbol] - consumed, 0.0)

        if action not in self.TOKEN_HOLD_REALIZED_ACTIONS:
            return 0.0

        value_for_consumed_amount = value * (consumed / amount) if amount > 0 else 0.0
        realized_pnl = value_for_consumed_amount - cost
        if pnl_by_symbol is not None:
            pnl_by_symbol[symbol] += realized_pnl
        return realized_pnl

    def _position_current_price(self, position: dict, symbol: str, value_usd: float, balance: float) -> float:
        if position.get("type") == "amm":
            return 0.0
        if balance > 0 and value_usd > 0:
            return value_usd / balance
        return self.pricing.get_price_safe(symbol, 0.0) if symbol else 0.0

    def get_chart_history(self, wallet: str, limit: int = 90) -> list[dict]:
        snapshots = self.portfolio_repository.get_daily_snapshots_chronological(wallet.lower(), limit=limit)

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
        token_hold = float(latest.get("token_hold_usd") or 0)
        lp = float(latest.get("total_amm_usd") or 0)
        vault = float(latest.get("total_vault_usd") or 0)
        supply_interest = float(latest.get("supply_interest_usd") or 0)
        borrow_interest = float(latest.get("borrow_interest_usd") or 0)
        supply_principal = float(latest.get("supply_principal_usd") or max(total_supply - supply_interest, 0))
        borrow_principal = float(latest.get("borrow_principal_usd") or max(total_borrow - borrow_interest, 0))
        calculated_total = token_hold + total_supply + lp + vault - total_borrow

        return {
            "totalUsd": round(float(latest.get("net_worth_usd") or calculated_total), 4),
            "calculatedTotalUsd": round(calculated_total, 4),
            "tokenHoldUsd": round(token_hold, 4),
            "supplyUsd": round(total_supply, 4),
            "lpUsd": round(lp, 4),
            "vaultUsd": round(vault, 4),
            "borrowUsd": round(total_borrow, 4),
            "lendingUsd": round(supply_principal, 4),
            "interestEarnedUsd": round(supply_interest, 4),
            "debtUsd": round(borrow_principal, 4),
            "debtInterestUsd": round(borrow_interest, 4),
            "farmingUsd": round(lp, 4),
        }

    def _build_pnl_summary(self, wallet: str, latest: dict) -> dict:
        current = float(latest.get("net_worth_usd") or 0)
        current_ts = int(latest.get("timestamp") or datetime.now(timezone.utc).timestamp())
        now = int(datetime.now(timezone.utc).timestamp())
        day = self.portfolio_repository.get_snapshot_at_or_before(wallet, now - 86400)
        week = self.portfolio_repository.get_snapshot_at_or_before(wallet, now - 86400 * 7)
        all_rows = self.portfolio_repository.get_snapshots_chronological(wallet, limit=1000)
        first = all_rows[0] if all_rows else None
        cashflow_rows = self.cashflow_repository.get_all_wallet_cashflows(wallet.lower())
        today = self._period_pnl(current, day, current_ts, cashflow_rows)
        seven_day = self._period_pnl(current, week, current_ts, cashflow_rows)
        all_time = self._period_pnl(current, first, current_ts, cashflow_rows)

        return {
            "todayUsd": today["pnlUsd"],
            "todayPct": today["pnlPct"],
            "todayExternalFlowUsd": today["netExternalFlowUsd"],
            "sevenDayUsd": seven_day["pnlUsd"],
            "sevenDayPct": seven_day["pnlPct"],
            "sevenDayExternalFlowUsd": seven_day["netExternalFlowUsd"],
            "allTimeUsd": all_time["pnlUsd"],
            "allTimePct": all_time["pnlPct"],
            "allTimeExternalFlowUsd": all_time["netExternalFlowUsd"],
            "roiPct": all_time["pnlPct"],
            "method": "net_worth_delta_minus_external_flow",
        }

    def _period_pnl(self, current: float, previous: dict | None, current_ts: int, cashflow_rows: list[dict]) -> dict:
        if not previous:
            return {
                "pnlUsd": 0.0,
                "pnlPct": 0.0,
                "externalDepositUsd": 0.0,
                "externalWithdrawUsd": 0.0,
                "netExternalFlowUsd": 0.0,
            }

        previous_value = float(previous.get("net_worth_usd") or 0)
        start_ts = int(previous.get("timestamp") or 0)
        external_flow = self._external_flow_from_events(cashflow_rows, start_ts=start_ts, end_ts=current_ts)
        pnl_usd = current - previous_value - external_flow["netExternalFlowUsd"]
        capital_base = previous_value + max(external_flow["externalDepositUsd"], 0.0)
        pnl_pct = (pnl_usd / capital_base * 100) if capital_base > 0 else 0.0

        return {
            "pnlUsd": round(pnl_usd, 4),
            "pnlPct": round(pnl_pct, 4),
            **external_flow,
        }

    def _external_flow_between(self, wallet: str, start_ts: int | None, end_ts: int | None) -> dict:
        rows = self.cashflow_repository.get_all_wallet_cashflows(wallet.lower())
        return self._external_flow_from_events(rows, start_ts=start_ts, end_ts=end_ts)

    def _external_flow_from_events(
        self,
        rows: list[dict],
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> dict:
        external_deposit = 0.0
        external_withdraw = 0.0

        for row in self._merge_events(rows):
            timestamp = int(row.get("timestamp") or 0)
            if start_ts is not None and timestamp <= start_ts:
                continue
            if end_ts is not None and timestamp > end_ts:
                continue
            if not self._is_external_capital_flow(row):
                continue

            amount_usd = self._estimated_value(row)
            if row.get("action") == "transfer_in":
                external_deposit += amount_usd
            elif row.get("action") == "transfer_out":
                external_withdraw += amount_usd

        return {
            "externalDepositUsd": round(external_deposit, 4),
            "externalWithdrawUsd": round(external_withdraw, 4),
            "netExternalFlowUsd": round(external_deposit - external_withdraw, 4),
        }

    def _is_external_capital_flow(self, row: dict) -> bool:
        if row.get("exclude_from_token_basis") or row.get("token_basis_note"):
            return False
        if row.get("action") not in ("transfer_in", "transfer_out"):
            return False
        event_source = row.get("event_source") or self._infer_event_source(row)
        if event_source != "onchain":
            return False
        category = row.get("transaction_category") or self._category(row.get("action"), event_source)
        return category == "transfer"

    def _format_transaction(
        self,
        row: dict,
        estimated_price: float,
        estimated_value: float,
        realized_pnl: float,
        price_quote: dict | None = None,
    ) -> dict:
        price_quote = price_quote or {}
        symbol = row.get("symbol")
        timestamp = int(row.get("timestamp") or 0)
        amount = float(row.get("amount") or 0)
        amount_usd = float(row.get("amount_usd") or 0)
        action = row.get("action")
        tx_id = row.get("tx_id") or row.get("tx_hash")
        event_source = row.get("event_source") or self._infer_event_source(row)
        category = row.get("transaction_category") or self._category(action, event_source)
        label = row.get("action_label") or self._action_label(action)
        tx_hash = row.get("tx_hash") or self._extract_tx_hash(row.get("tx_id"))
        direction = row.get("direction") or self._direction(action)
        log_index = row.get("log_index")
        market_id = row.get("market_id") or row.get("pool_id")
        protocol = row.get("protocol") or row.get("event_source") or event_source
        pool_key = market_id or self._source_label(row, event_source)
        pool_label = self._pool_label(row, event_source)
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
            "protocol": protocol,
            "marketId": market_id,
            "poolId": row.get("pool_id"),
            "poolKey": pool_key,
            "poolLabel": pool_label,
            "direction": direction,
            "description": self._describe_action(action, symbol),
            "symbol": symbol,
            "amount": amount,
            "amountUsd": round(estimated_value, 4),
            "recordedAmountUsd": round(amount_usd, 4),
            "priceAtTx": round(estimated_price, 8) if estimated_price else None,
            "estimatedExecutionPrice": round(estimated_price, 8) if estimated_price else None,
            "priceSource": price_quote.get("priceSource") or row.get("price_source") or ("historical_snapshot" if estimated_price else "recorded_amount"),
            "priceTimestamp": price_quote.get("priceTimestamp"),
            "priceDeltaSeconds": price_quote.get("priceDeltaSeconds"),
            "priceMaxDeltaSeconds": price_quote.get("priceMaxDeltaSeconds"),
            "priceReliable": price_quote.get("priceReliable"),
            "priceNote": price_quote.get("priceNote"),
            "realizedPnlUsd": round(realized_pnl, 4),
            "timestamp": timestamp,
            "type": self._transaction_type(action),
            "timeAgo": self._time_ago(timestamp),
            "source": self._source_label(row, event_source),
            "from": row.get("from"),
            "to": row.get("to"),
            "gasCostEth": round(float(row.get("gas_cost_eth") or 0), 10),
            "gasCostUsd": round(float(row.get("gas_cost_usd") or row.get("protocol_fee_usd") or 0), 8),
            "explorerUrl": f"https://etherscan.io/tx/{tx_hash}" if tx_hash else None,
            "tokenBasisExcluded": bool(row.get("exclude_from_token_basis")),
            "tokenBasisNote": row.get("token_basis_note"),
        }

    def _calculate_basis_and_realized_by_symbol(self, wallet: str) -> tuple[dict[str, float], dict[str, float], dict[str, dict]]:
        basis_by_symbol = {}
        amount_by_symbol = {}
        pnl_by_symbol = {}
        meta_by_symbol = {}

        for row in self._token_basis_events(wallet):
            symbol = row.get("symbol")
            if not symbol:
                continue

            action = row.get("action")
            amount = float(row.get("amount") or 0)
            value = self._estimated_value(row)

            basis_by_symbol.setdefault(symbol, 0.0)
            amount_by_symbol.setdefault(symbol, 0.0)
            pnl_by_symbol.setdefault(symbol, 0.0)
            meta = meta_by_symbol.setdefault(symbol, {
                "has_known_cost": False,
                "has_unknown_cost": False,
                "has_unmatched_sell": False,
                "has_unreliable_price": False,
            })
            price_reliable = self._row_price_reliable(row)

            if action in self.TOKEN_HOLD_UNKNOWN_COST_ACTIONS and amount > 0:
                meta["has_unknown_cost"] = True
                continue

            if action == "buy":
                if value <= 0:
                    meta["has_unknown_cost"] = True
                    continue
                if not price_reliable:
                    meta["has_unreliable_price"] = True
                    continue
                meta["has_known_cost"] = True

            if action == "sell" and not price_reliable:
                meta["has_unreliable_price"] = True

            if action == "sell" and amount_by_symbol.get(symbol, 0.0) <= 0:
                meta["has_unmatched_sell"] = True

            self._apply_token_hold_basis_event(
                symbol=symbol,
                action=action,
                amount=amount,
                value=value,
                basis_by_symbol=basis_by_symbol,
                amount_by_symbol=amount_by_symbol,
                pnl_by_symbol=pnl_by_symbol,
            )

        basis_meta_by_symbol = {}
        for symbol in set(basis_by_symbol) | set(pnl_by_symbol) | set(meta_by_symbol):
            meta = meta_by_symbol.get(symbol, {})
            has_known_cost = bool(meta.get("has_known_cost"))
            has_unknown_cost = bool(meta.get("has_unknown_cost"))
            has_unmatched_sell = bool(meta.get("has_unmatched_sell"))
            has_unreliable_price = bool(meta.get("has_unreliable_price"))
            reliable = has_known_cost and not has_unknown_cost and not has_unmatched_sell and not has_unreliable_price
            if has_unknown_cost:
                note = "Token PnL unavailable: wallet has receive/withdraw/borrow inflow with unknown basis"
            elif has_unreliable_price:
                note = "Token PnL unavailable: priceAtTx snapshot is missing or outside the configured time delta"
            elif not has_known_cost:
                note = "Token PnL unavailable: no verified buy cost basis"
            elif has_unmatched_sell:
                note = "Token PnL unavailable: sell exceeds verified held basis"
            else:
                note = "Average-cost basis from verified buy/sell cashflow"
            basis_meta_by_symbol[symbol] = {
                "reliable": reliable,
                "note": note,
            }

        return (
            {symbol: max(value, 0.0) for symbol, value in basis_by_symbol.items()},
            pnl_by_symbol,
            basis_meta_by_symbol,
        )

    def _calculate_symbol_cost_basis(self, wallet: str, symbol: str) -> float:
        basis = 0.0
        held_amount = 0.0

        for row in self._token_basis_events(wallet):
            if row.get("symbol") != symbol:
                continue

            action = row.get("action")
            amount = float(row.get("amount") or 0)
            value = self._estimated_value(row)

            basis_by_symbol = {symbol: basis}
            amount_by_symbol = {symbol: held_amount}
            self._apply_token_hold_basis_event(
                symbol=symbol,
                action=action,
                amount=amount,
                value=value,
                basis_by_symbol=basis_by_symbol,
                amount_by_symbol=amount_by_symbol,
            )
            basis = basis_by_symbol[symbol]
            held_amount = amount_by_symbol[symbol]

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

            self._apply_token_hold_basis_event(
                symbol=symbol,
                action=action,
                amount=amount,
                value=value,
                basis_by_symbol=basis_by_symbol,
                amount_by_symbol=amount_by_symbol,
                pnl_by_symbol=pnl_by_symbol,
            )

        return pnl_by_symbol

    def _estimated_value(self, row: dict) -> float:
        price = float(self._price_quote_for_row(row).get("price") or 0)
        amount = float(row.get("amount") or 0)
        if price > 0:
            return amount * price

        return float(row.get("amount_usd") or 0)

    def _price_quote_for_row(self, row: dict) -> dict:
        timestamp = int(row.get("timestamp") or 0)
        stored_price = float(row.get("price_at_tx") or row.get("priceAtTx") or 0)
        if stored_price > 0:
            delta = self._optional_int(self._first_present(row, "price_delta_seconds", "priceDeltaSeconds"))
            max_delta = self._optional_int(self._first_present(row, "price_max_delta_seconds", "priceMaxDeltaSeconds"))
            reliable = self._optional_bool(self._first_present(row, "price_reliable", "priceReliable"))
            if reliable is None and delta is not None and max_delta is not None:
                reliable = delta <= max_delta
            return {
                "price": stored_price,
                "priceSource": row.get("price_source") or row.get("priceSource") or "historical_snapshot",
                "priceTimestamp": self._optional_int(self._first_present(row, "price_timestamp", "priceTimestamp")),
                "priceDeltaSeconds": delta,
                "priceMaxDeltaSeconds": max_delta,
                "priceReliable": bool(reliable) if reliable is not None else False,
                "priceNote": row.get("price_note") or row.get("priceNote"),
            }

        pricing = getattr(self, "pricing", None)
        if not pricing:
            return {
                "price": 0.0,
                "priceSource": "missing_snapshot",
                "priceTimestamp": None,
                "priceDeltaSeconds": None,
                "priceMaxDeltaSeconds": None,
                "priceReliable": False,
                "priceNote": "No pricing service available",
            }
        return pricing.get_historical_price_quote(row.get("symbol"), timestamp)

    def _row_price_reliable(self, row: dict) -> bool:
        return bool(self._price_quote_for_row(row).get("priceReliable"))

    def _optional_int(self, value) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def _optional_bool(self, value) -> bool | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "y")
        return bool(value)

    def _first_present(self, row: dict, *keys):
        for key in keys:
            value = row.get(key)
            if value is not None:
                return value
        return None

    def _token_basis_events(self, wallet: str) -> list[dict]:
        cashflows = self.cashflow_repository.get_wallet_cashflows_chronological(wallet)
        return [row for row in self._merge_events(cashflows) if not row.get("exclude_from_token_basis")]

    def _merge_events(self, cashflows: list[dict]) -> list[dict]:
        events = []

        for row in cashflows:
            item = dict(row)
            item["event_source"] = item.get("event_source") or self._infer_event_source(item)
            item["transaction_category"] = item.get("transaction_category") or self._category(
                item.get("action"),
                item["event_source"],
            )
            item["action_label"] = item.get("action_label") or self._action_label(item.get("action"))
            events.append(item)

        self._downgrade_single_sided_onchain_swaps(events)
        self._mark_protocol_shadow_transfers(events)

        events.sort(key=lambda item: (
            int(item.get("timestamp") or 0),
            str(item.get("tx_id") or item.get("tx_hash") or ""),
            int(item.get("log_index") or -1),
        ))
        return events

    def _downgrade_single_sided_onchain_swaps(self, events: list[dict]):
        by_hash = {}
        for item in events:
            if (item.get("event_source") or self._infer_event_source(item)) != "onchain":
                continue
            tx_hash = self._event_tx_hash(item)
            if not tx_hash:
                continue
            by_hash.setdefault(tx_hash, []).append(item)

        for tx_events in by_hash.values():
            has_buy = any(item.get("action") == "buy" for item in tx_events)
            has_sell = any(item.get("action") == "sell" for item in tx_events)
            if has_buy and has_sell:
                continue

            for item in tx_events:
                if item.get("action") == "buy":
                    self._retag_event_action(item, "transfer_in", "single_sided_onchain_swap")
                elif item.get("action") == "sell":
                    self._retag_event_action(item, "transfer_out", "single_sided_onchain_swap")

    def _mark_protocol_shadow_transfers(self, events: list[dict]):
        protocol_hashes = {
            self._event_tx_hash(item)
            for item in events
            if (item.get("event_source") or self._infer_event_source(item)) == "protocol"
        }
        protocol_hashes.discard(None)
        if not protocol_hashes:
            return

        for item in events:
            if (item.get("event_source") or self._infer_event_source(item)) != "onchain":
                continue
            if self._event_tx_hash(item) not in protocol_hashes:
                continue
            item["exclude_from_token_basis"] = True
            item["token_basis_note"] = "covered_by_protocol_cashflow"

    def _retag_event_action(self, item: dict, action: str, note: str):
        item["action"] = action
        item["action_label"] = self._action_label(action)
        item["transaction_category"] = self._category(action, item.get("event_source") or self._infer_event_source(item))
        item["direction"] = self._direction(action)
        item["token_basis_note"] = note

    def _event_tx_hash(self, item: dict) -> str | None:
        return item.get("tx_hash") or item.get("txHash") or self._extract_tx_hash(item.get("tx_id") or item.get("txId"))

    def _infer_event_source(self, row: dict) -> str:
        source = str(row.get("source") or "").lower()
        action = str(row.get("action") or "").lower()
        category = str(row.get("transaction_category") or "").lower()
        if row.get("asset_type") or source == "etherscan" or category in ("transfer", "swap", "onchain"):
            return "onchain"
        if action in ("transfer_in", "transfer_out", "buy", "sell"):
            return "onchain"
        return "protocol"

    def _extract_tx_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"0x[a-fA-F0-9]{64}", str(value))
        return match.group(0).lower() if match else None

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

    def _pool_label(self, row: dict, event_source: str) -> str:
        if row.get("pool_label"):
            return row["pool_label"]
        if row.get("market_id") or row.get("pool_id"):
            protocol = row.get("protocol") or event_source
            symbol = row.get("symbol") or row.get("asset") or ""
            return f"{protocol} {symbol}".strip()
        if row.get("transaction_category") == "swap" or row.get("action") in ("buy", "sell"):
            return "On-chain swaps"
        if row.get("transaction_category") == "transfer" or row.get("action") in ("transfer_in", "transfer_out"):
            return "Wallet transfers"
        return self._source_label(row, event_source)

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
