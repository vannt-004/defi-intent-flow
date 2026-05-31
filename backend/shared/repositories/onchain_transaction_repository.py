from pymongo import ASCENDING, DESCENDING, UpdateOne

from shared.databases.base_repository import BaseRepository


class OnchainTransactionRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "onchain_transactions")
        self.collection.create_index(
            [
                ("wallet", 1),
                ("tx_hash", 1),
                ("log_index", 1),
                ("asset_type", 1),
                ("direction", 1),
            ],
            unique=True,
        )
        self.collection.create_index([("wallet", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("block_number", -1)])

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []
        for item in items:
            operations.append(
                UpdateOne(
                    {
                        "wallet": item["wallet"],
                        "tx_hash": item["tx_hash"],
                        "log_index": item["log_index"],
                        "asset_type": item["asset_type"],
                        "direction": item["direction"],
                    },
                    {"$set": item},
                    upsert=True,
                )
            )

        return self.collection.bulk_write(operations, ordered=False)

    def get_wallet_transactions(self, wallet: str, limit: int = 100) -> list[dict]:
        return list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

    def get_wallet_transactions_chronological(self, wallet: str) -> list[dict]:
        return list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort([("timestamp", ASCENDING), ("log_index", ASCENDING)])
        )

    def get_latest_block(self, wallet: str) -> int:
        row = self.collection.find_one(
            {"wallet": wallet},
            {"block_number": 1},
            sort=[("block_number", DESCENDING)],
        )

        return int(row.get("block_number") or 0) if row else 0
