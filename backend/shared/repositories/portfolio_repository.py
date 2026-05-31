from pymongo import DESCENDING, UpdateOne

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class PortfolioRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "portfolio_snapshot")

        self.collection.create_index([("wallet", 1), ("timestamp", -1), ])

    def insert_snapshot(self, snapshot: dict):
        return self.collection.insert_one(keys_to_camel(snapshot))

    def upsert_snapshot(self, snapshot: dict):
        return self.collection.update_one(
            {"wallet": snapshot["wallet"], "timestamp": snapshot["timestamp"]},
            {"$set": keys_to_camel(snapshot)},
            upsert=True,
        )

    def get_latest_snapshot(self, wallet: str, ) -> dict | None:
        row = self.collection.find_one({"wallet": wallet}, {"_id": 0}, sort=[("timestamp", DESCENDING)])
        return keys_to_snake(row) if row else None

    def get_snapshots(self, wallet: str, limit: int = 30, ) -> list[dict]:
        rows = self.collection.find({"wallet": wallet}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
        return [keys_to_snake(row) for row in rows]

    def get_snapshots_chronological(self, wallet: str, limit: int = 90) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        return [keys_to_snake(row) for row in reversed(rows)]

    def get_snapshot_at_or_before(self, wallet: str, timestamp: int) -> dict | None:
        row = self.collection.find_one(
            {"wallet": wallet, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
        return keys_to_snake(row) if row else None
