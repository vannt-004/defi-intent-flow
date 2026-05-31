from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository


class PortfolioRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "portfolio_snapshot")

        self.collection.create_index([("wallet", 1), ("timestamp", -1), ])

    def insert_snapshot(self, snapshot: dict):
        return self.collection.insert_one(snapshot)

    def get_latest_snapshot(self, wallet: str, ) -> dict | None:
        return self.collection.find_one({"wallet": wallet, }, sort=[("timestamp", DESCENDING), ], )

    def get_snapshots(self, wallet: str, limit: int = 30, ) -> list[dict]:
        return list(self.collection.find({"wallet": wallet, }).sort("timestamp", DESCENDING).limit(limit))

    def get_snapshots_chronological(self, wallet: str, limit: int = 90) -> list[dict]:
        rows = list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        return list(reversed(rows))

    def get_snapshot_at_or_before(self, wallet: str, timestamp: int) -> dict | None:
        return self.collection.find_one(
            {"wallet": wallet, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
