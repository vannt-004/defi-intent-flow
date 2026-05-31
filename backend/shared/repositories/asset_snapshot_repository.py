from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository


class AssetSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "asset_snapshot")

        self.collection.create_index([("wallet", 1), ("symbol", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("timestamp", -1)])

    def bulk_insert(self, items: list[dict]):
        if not items:
            return None

        return self.collection.insert_many(items)

    def get_latest_asset_snapshot(self, wallet: str, symbol: str) -> dict | None:
        return self.collection.find_one(
            {"wallet": wallet, "symbol": symbol},
            sort=[("timestamp", DESCENDING)],
        )

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
            {"$sort": {"value_usd": -1}},
        ]

        return list(self.collection.aggregate(pipeline))
