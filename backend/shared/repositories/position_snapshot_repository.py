from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository


class PositionSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "position_snapshot")

        self.collection.create_index([("wallet", 1), ("position_id", 1), ("timestamp", -1), ])

        self.collection.create_index([("wallet", 1), ("timestamp", -1), ])

    def bulk_insert(self, items: list[dict]):
        if not items:
            return None

        return self.collection.insert_many(items)

    def get_latest_position_snapshot(self, wallet: str, position_id: str) -> dict | None:
        return self.collection.find_one({"wallet": wallet, "position_id": position_id, },
            sort=[("timestamp", DESCENDING), ], )

    def get_latest_wallet_positions(self, wallet: str) -> list[dict]:
        pipeline = [
            {"$match": {"wallet": wallet}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$position_id",
                    "position": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$position"}},
            {"$sort": {"value_usd": -1}},
            {"$project": {"_id": 0}},
        ]

        return list(self.collection.aggregate(pipeline))
