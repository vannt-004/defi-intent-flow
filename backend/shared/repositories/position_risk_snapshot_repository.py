from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class PositionRiskSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "position_risk_snapshot")
        self.collection.create_index([("wallet", 1), ("positionId", 1), ("timestamp", -1)])
        self.collection.create_index([("wallet", 1), ("timestamp", -1)])

    def bulk_insert(self, items: list[dict]):
        if not items:
            return None

        return self.collection.insert_many([keys_to_camel(item) for item in items])

    def get_latest_wallet_risks(self, wallet: str) -> list[dict]:
        pipeline = [
            {"$match": {"wallet": wallet, "scope": "position"}},
            {"$sort": {"timestamp": -1}},
            {
                "$group": {
                    "_id": "$positionId",
                    "risk": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$risk"}},
            {"$sort": {"riskScore": -1}},
            {"$project": {"_id": 0}},
        ]

        return [keys_to_snake(row) for row in self.collection.aggregate(pipeline)]

    def get_portfolio_risk_history(self, wallet: str, limit: int = 90) -> list[dict]:
        cursor = (
            self.collection.find(
                {"wallet": wallet, "scope": "portfolio"},
                {"_id": 0},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

        return [keys_to_snake(row) for row in reversed(list(cursor))]
