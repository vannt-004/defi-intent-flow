from shared.repositories.wallet_repository import WalletRepository
from shared.databases.mongo_client import MongoConnection


class WalletService:

    def __init__(self):
        db = MongoConnection.get_database()

        self.wallet_repository = WalletRepository(db)

    async def add_wallet(self, wallet: str):
        self.wallet_repository.add_wallet(wallet)

        return {"success": True, "wallet": wallet.lower()}

    async def get_wallets(self):
        wallets = self.wallet_repository.get_active_wallets()

        return {"count": len(wallets), "wallets": wallets}
