from pymongo import DESCENDING, UpdateOne

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class AssetSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "asset_snapshot")

        self.collection.create_index([("wallet", 1), ("symbol", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("timestamp", -1)])

    def bulk_insert(self, items: list[dict]):
        if not items:
            return None

        return self.collection.insert_many([keys_to_camel(item) for item in items])

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []
        for item in items:
            operations.append(
                UpdateOne(
                    {"wallet": item["wallet"], "symbol": item["symbol"], "timestamp": item["timestamp"]},
                    {"$set": keys_to_camel(item)},
                    upsert=True,
                )
            )

        return self.collection.bulk_write(operations, ordered=False)

    def get_latest_asset_snapshot(self, wallet: str, symbol: str) -> dict | None:
        row = self.collection.find_one(
            {"wallet": wallet, "symbol": symbol},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
        return keys_to_snake(row) if row else None

    def get_latest_wallet_assets(self, wallet: str) -> list[dict]:
        pipeline = [
            {"$match": {"wallet": wallet}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$symbol",
                    "asset": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$asset"}},
            {"$sort": {"valueUsd": -1}},
            {"$project": {"_id": 0}},
        ]

        return [keys_to_snake(row) for row in self.collection.aggregate(pipeline)]
