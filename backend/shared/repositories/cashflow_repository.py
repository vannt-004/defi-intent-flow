from pymongo import UpdateOne
from pymongo import DESCENDING

from shared.databases.base_repository import BaseRepository


class CashflowRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "cashflow")

        self.collection.create_index([("wallet", 1), ("tx_id", 1), ("action", 1), ], unique=True, )

        self.collection.create_index([("wallet", 1), ("timestamp", -1), ])

    def bulk_upsert(self, items: list[dict]):
        if not items:
            return None

        operations = []

        for item in items:
            operations.append(UpdateOne({"wallet": item["wallet"], "tx_id": item["tx_id"], "action": item["action"], },
                                        {"$set": item, }, upsert=True, ))

        return self.collection.bulk_write(operations, ordered=False, )

    def get_wallet_cashflows(self, wallet: str, limit: int = 100) -> list[dict]:
        return list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

    def get_wallet_cashflows_chronological(self, wallet: str) -> list[dict]:
        return list(
            self.collection.find({"wallet": wallet}, {"_id": 0})
            .sort("timestamp", 1)
        )
