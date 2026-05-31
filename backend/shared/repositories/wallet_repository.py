from datetime import datetime, timezone

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_snake


class WalletRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "wallets")

        self.collection.create_index([("wallet", 1)], unique=True, )

        self.collection.create_index([("isActive", 1)])
        self.collection.create_index([("status", 1)])

    def add_wallet(self, wallet: str, ):
        wallet = wallet.lower()

        return self.collection.update_one({"wallet": wallet, },
            {"$set": {"_id": wallet, "wallet": wallet, "isActive": True, "status": "synced", "updatedAt": datetime.now(timezone.utc), },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc), }, }, upsert=True, )

    def queue_wallet(self, wallet: str):
        wallet = wallet.lower()
        return self.collection.update_one(
            {"wallet": wallet},
            {
                "$set": {
                    "_id": wallet,
                    "wallet": wallet,
                    "isActive": False,
                    "status": "queued",
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc)},
            },
            upsert=True,
        )

    def get_wallet(self, wallet: str) -> dict | None:
        row = self.collection.find_one({"wallet": wallet.lower()}, {"_id": 0})
        return keys_to_snake(row) if row else None

    def get_active_wallets(self, limit: int = 1000, ) -> list[str]:
        rows = self.collection.find({"isActive": True}, {"wallet": 1}).limit(limit)

        return [row["wallet"] for row in rows]

    def disable_wallet(self, wallet: str, ):
        return self.collection.update_one({"wallet": wallet.lower(), },
            {"$set": {"isActive": False, "status": "disabled", "updatedAt": datetime.now(timezone.utc)}}, )
