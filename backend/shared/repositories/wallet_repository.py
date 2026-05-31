from datetime import datetime, timezone

from shared.databases.base_repository import BaseRepository


class WalletRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "wallets")

        self.collection.create_index([("wallet", 1)], unique=True, )

        self.collection.create_index([("is_active", 1), ])

    def add_wallet(self, wallet: str, ):
        wallet = wallet.lower()

        return self.collection.update_one({"wallet": wallet, },
            {"$set": {"_id": wallet, "wallet": wallet, "is_active": True, "updated_at": datetime.now(timezone.utc), },
                "$setOnInsert": {"created_at": datetime.now(timezone.utc), }, }, upsert=True, )

    def get_active_wallets(self, limit: int = 1000, ) -> list[str]:
        rows = self.collection.find({"is_active": True, }, {"wallet": 1, }, ).limit(limit)

        return [row["wallet"] for row in rows]

    def disable_wallet(self, wallet: str, ):
        return self.collection.update_one({"wallet": wallet.lower(), },
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc), }}, )
