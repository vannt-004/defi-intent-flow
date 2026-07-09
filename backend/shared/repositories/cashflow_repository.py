import re

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
        self.collection.create_index([("wallet", 1), ("symbol", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("eventSource", 1), ("blockNumber", -1)])
        self.collection.create_index([("wallet", 1), ("txHash", 1), ("logIndex", 1)])
        self.collection.create_index([("positionId", 1), ("timestamp", -1)])

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

    def get_wallet_watermark(self, wallet: str) -> dict:
        wallet = wallet.lower()
        latest = self.collection.find_one(
            {"wallet": wallet},
            {"_id": 0, "timestamp": 1, "txId": 1, "txHash": 1, "logIndex": 1},
            sort=[("timestamp", DESCENDING), ("txId", DESCENDING), ("logIndex", DESCENDING)],
        ) or {}
        latest_block = self.collection.find_one(
            {"wallet": wallet, "blockNumber": {"$exists": True}},
            {"_id": 0, "blockNumber": 1},
            sort=[("blockNumber", DESCENDING)],
        ) or {}

        return {
            "count": self.collection.count_documents({"wallet": wallet}),
            "latestTimestamp": int(latest.get("timestamp") or 0),
            "latestBlockNumber": int(latest_block.get("blockNumber") or 0),
            "latestTxId": latest.get("txId"),
            "latestTxHash": latest.get("txHash"),
            "latestLogIndex": latest.get("logIndex"),
        }

    def get_cashflows_by_tx_hashes(self, tx_hashes: list[str]) -> list[dict]:
        hashes = [tx_hash.lower() for tx_hash in tx_hashes if tx_hash]
        if not hashes:
            return []

        rows = list(
            self.collection.find(
                {
                    "$or": [
                        {"txHash": {"$in": hashes}},
                        {"txId": {"$in": hashes}},
                        *[{"txId": {"$regex": re.escape(tx_hash), "$options": "i"}} for tx_hash in hashes],
                    ]
                },
                {"_id": 0},
            )
        )
        return [keys_to_snake(row) for row in rows]

    def get_missing_gas_tx_hashes(self, limit: int = 500) -> list[dict]:
        rows = list(
            self.collection.find(
                {
                    "$and": [
                        {
                            "$or": [
                                {"gasCostUsd": {"$exists": False}},
                                {"gasCostUsd": None},
                                {"gasCostUsd": 0},
                            ],
                        },
                        {
                            "$or": [
                                {"txHash": {"$exists": True, "$ne": None}},
                                {"txId": {"$regex": "0x[a-fA-F0-9]{64}"}},
                            ],
                        },
                    ],
                },
                {"_id": 0, "wallet": 1, "txHash": 1, "txId": 1, "timestamp": 1},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        unique = {}
        for row in rows:
            tx_hash = row.get("txHash") or self._extract_tx_hash(row.get("txId"))
            if not tx_hash:
                continue
            unique[tx_hash.lower()] = {
                "wallet": row.get("wallet"),
                "txHash": tx_hash.lower(),
                "timestamp": int(row.get("timestamp") or 0),
            }
        return list(unique.values())

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

    def backfill_gas_by_tx_hash(self, wallet: str, gas_by_hash: dict[str, dict]):
        if not gas_by_hash:
            return None

        rows = list(
            self.collection.find(
                {"wallet": wallet},
                {"_id": 1, "txId": 1, "txHash": 1, "gasCostUsd": 1, "gasCostEth": 1},
            )
        )
        operations = []

        for row in rows:
            tx_hash = row.get("txHash") or self._extract_tx_hash(row.get("txId"))
            if not tx_hash:
                continue
            gas = gas_by_hash.get(tx_hash.lower())
            if not gas:
                continue
            if float(row.get("gasCostUsd") or 0) > 0 and row.get("txHash"):
                continue

            operations.append(UpdateOne(
                {"_id": row["_id"]},
                {"$set": {
                    "txHash": tx_hash.lower(),
                    "gasCostEth": float(gas.get("gasCostEth") or 0),
                    "gasCostUsd": float(gas.get("gasCostUsd") or 0),
                }},
            ))

        return self.collection.bulk_write(operations, ordered=False) if operations else None

    def update_gas_by_tx_hash(self, tx_hash: str, gas_cost_eth: float, gas_cost_usd: float):
        tx_hash = tx_hash.lower()
        return self.collection.update_many(
            {
                "$or": [
                    {"txHash": tx_hash},
                    {"txId": tx_hash},
                    {"txId": {"$regex": re.escape(tx_hash), "$options": "i"}},
                ]
            },
            {
                "$set": {
                    "txHash": tx_hash,
                    "gasCostEth": round(float(gas_cost_eth or 0), 10),
                    "gasCostUsd": round(float(gas_cost_usd or 0), 6),
                }
            },
        )

    def _extract_tx_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"0x[a-fA-F0-9]{64}", str(value))
        return match.group(0).lower() if match else None

    def _median(self, values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2
