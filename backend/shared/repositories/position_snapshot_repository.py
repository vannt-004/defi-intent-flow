from pymongo import DESCENDING, UpdateOne

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake, sanitize_mongo_numbers


class PositionSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "position_snapshot")

        self.collection.create_index([("wallet", 1), ("positionId", 1), ("timestamp", -1), ])

        self.collection.create_index([("wallet", 1), ("timestamp", -1), ])

    def bulk_insert(self, items: list[dict]):
        if not items:
            return None

        return self.collection.insert_many([
            sanitize_mongo_numbers(keys_to_camel(item)) for item in items
        ])

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []
        for item in items:
            operations.append(
                UpdateOne(
                    {
                        "wallet": item["wallet"],
                        "positionId": item["position_id"],
                        "timestamp": item["timestamp"],
                    },
                    {"$set": sanitize_mongo_numbers(keys_to_camel(item))},
                    upsert=True,
                )
            )

        return self.collection.bulk_write(operations, ordered=False)

    def get_latest_position_snapshot(self, wallet: str, position_id: str) -> dict | None:
        row = self.collection.find_one(
            {"wallet": wallet, "positionId": position_id},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
        return keys_to_snake(row) if row else None

    def get_latest_wallet_positions(self, wallet: str) -> list[dict]:
        pipeline = [
            {"$match": {"wallet": wallet}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$positionId",
                    "position": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$position"}},
            {"$sort": {"valueUsd": -1}},
            {"$project": {"_id": 0}},
        ]

        return [keys_to_snake(row) for row in self.collection.aggregate(pipeline)]

    def get_wallet_position_history(self, wallet: str, position_id: str, limit: int = 90) -> list[dict]:
        cursor = (
            self.collection.find(
                {"wallet": wallet, "positionId": position_id},
                {"_id": 0},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        return [keys_to_snake(row) for row in reversed(list(cursor))]
