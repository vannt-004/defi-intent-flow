from pymongo import UpdateOne
from pymongo import DESCENDING
from pymongo.errors import OperationFailure

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class CashflowRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "cashflow")

        self._drop_legacy_indexes()
        self.collection.create_index([("wallet", 1), ("txId", 1), ("action", 1)], unique=True)

        self.collection.create_index([("wallet", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("eventSource", 1), ("blockNumber", -1)])

    def _drop_legacy_indexes(self):
        for index_name in ("wallet_1_tx_id_1_action_1", "wallet_1_event_source_1_block_number_-1"):
            try:
                self.collection.drop_index(index_name)
            except OperationFailure:
                pass

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []

        for item in items:
            operations.append(UpdateOne(
                {"wallet": item["wallet"], "txId": item["tx_id"], "action": item["action"]},
                {"$set": keys_to_camel(item)},
                upsert=True,
            ))

        return self.collection.bulk_write(operations, ordered=False, )

    def get_wallet_cashflows(self, wallet: str, limit: int = 100) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        return [keys_to_snake(row) for row in rows]

    def get_all_wallet_cashflows(self, wallet: str) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
        )
        return [keys_to_snake(row) for row in rows]

    def get_wallet_cashflows_chronological(self, wallet: str) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", 1)
        )
        return [keys_to_snake(row) for row in rows]

    def get_latest_onchain_block(self, wallet: str) -> int:
        row = self.collection.find_one(
            {"wallet": wallet, "eventSource": "onchain", "blockNumber": {"$exists": True}},
            {"blockNumber": 1},
            sort=[("blockNumber", DESCENDING)],
        )
        return int(row.get("blockNumber") or 0) if row else 0

    def get_wallet_fee_stats(self, wallet: str, limit: int = 500) -> dict:
        rows = list(
            self.collection.find(
                {
                    "wallet": wallet,
                    "$or": [
                        {"gasCostEth": {"$gt": 0}},
                        {"gasCostUsd": {"$gt": 0}},
                        {"protocolFeeUsd": {"$gt": 0}},
                    ],
                },
                {"_id": 0, "txId": 1, "txHash": 1, "gasCostEth": 1, "gasCostUsd": 1, "protocolFeeUsd": 1},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        unique_by_tx = {}
        for row in rows:
            tx_key = row.get("txHash") or row.get("txId")
            if not tx_key or tx_key in unique_by_tx:
                continue
            unique_by_tx[tx_key] = row

        unique_rows = list(unique_by_tx.values())
        gas_usd = [float(row.get("gasCostUsd") or 0) for row in unique_rows if float(row.get("gasCostUsd") or 0) > 0]
        gas_eth = [float(row.get("gasCostEth") or 0) for row in unique_rows if float(row.get("gasCostEth") or 0) > 0]
        protocol_fee_usd = [
            float(row.get("protocolFeeUsd") or 0)
            for row in unique_rows
            if float(row.get("protocolFeeUsd") or 0) > 0
        ]

        return {
            "sample_count": len(unique_rows),
            "avg_gas_usd": round(sum(gas_usd) / len(gas_usd), 6) if gas_usd else 0.0,
            "median_gas_usd": round(self._median(gas_usd), 6) if gas_usd else 0.0,
            "max_gas_usd": round(max(gas_usd), 6) if gas_usd else 0.0,
            "avg_gas_eth": round(sum(gas_eth) / len(gas_eth), 10) if gas_eth else 0.0,
            "median_gas_eth": round(self._median(gas_eth), 10) if gas_eth else 0.0,
            "avg_protocol_fee_usd": round(sum(protocol_fee_usd) / len(protocol_fee_usd), 6) if protocol_fee_usd else 0.0,
            "median_protocol_fee_usd": round(self._median(protocol_fee_usd), 6) if protocol_fee_usd else 0.0,
        }

    def _median(self, values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2
