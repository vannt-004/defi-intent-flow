from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.errors import OperationFailure

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class OnchainTransactionRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "onchain_transactions")
        self._drop_legacy_indexes()
        self.collection.create_index(
            [
                ("wallet", 1),
                ("txHash", 1),
                ("logIndex", 1),
                ("assetType", 1),
                ("direction", 1),
            ],
            unique=True,
        )
        self.collection.create_index([("wallet", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("blockNumber", -1)])

    def _drop_legacy_indexes(self):
        for index_name in (
            "wallet_1_tx_hash_1_log_index_1_asset_type_1_direction_1",
            "wallet_1_block_number_-1",
        ):
            try:
                self.collection.drop_index(index_name)
            except OperationFailure:
                pass

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []
        for item in items:
            operations.append(
                UpdateOne(
                    {
                        "wallet": item["wallet"],
                        "txHash": item["tx_hash"],
                        "logIndex": item["log_index"],
                        "assetType": item["asset_type"],
                        "direction": item["direction"],
                    },
                    {"$set": keys_to_camel(item)},
                    upsert=True,
                )
            )

        return self.collection.bulk_write(operations, ordered=False)

    def get_wallet_transactions(self, wallet: str, limit: int = 100) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        return [keys_to_snake(row) for row in rows]

    def get_wallet_transactions_chronological(self, wallet: str) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort([("timestamp", ASCENDING), ("logIndex", ASCENDING)])
        )
        return [keys_to_snake(row) for row in rows]

    def get_latest_block(self, wallet: str) -> int:
        row = self.collection.find_one(
            {"wallet": wallet},
            {"blockNumber": 1},
            sort=[("blockNumber", DESCENDING)],
        )

        return int(row.get("blockNumber") or 0) if row else 0
