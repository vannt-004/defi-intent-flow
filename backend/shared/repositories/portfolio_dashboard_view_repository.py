from datetime import datetime, timezone

from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository


class PortfolioDashboardViewRepository(BaseRepository):
    SCHEMA_VERSION = 13

    def __init__(self, db):
        super().__init__(db, "portfolio_dashboard_view")
        self.collection.create_index([("wallet", 1)], unique=True)
        self.collection.create_index([("wallet", 1), ("sourceTimestamp", -1)])
        self.collection.create_index([("updatedAt", DESCENDING)])

    def get_view(self, wallet: str) -> dict | None:
        row = self.collection.find_one({"wallet": wallet.lower()}, {"_id": 0})
        return row.get("payload") if row else None

    def get_view_row(self, wallet: str) -> dict | None:
        return self.collection.find_one({"wallet": wallet.lower()}, {"_id": 0})

    def upsert_view(
        self,
        wallet: str,
        payload: dict,
        source_timestamp: int | None = None,
        metadata: dict | None = None,
    ):
        now = datetime.now(timezone.utc)
        return self.collection.update_one(
            {"wallet": wallet.lower()},
            {
                "$set": {
                    "wallet": wallet.lower(),
                    "sourceTimestamp": source_timestamp,
                    "schemaVersion": self.SCHEMA_VERSION,
                    "payload": payload,
                    "metadata": metadata or {},
                    "updatedAt": now,
                },
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )

    def invalidate(self, wallet: str):
        return self.collection.delete_one({"wallet": wallet.lower()})
