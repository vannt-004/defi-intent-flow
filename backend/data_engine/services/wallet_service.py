from shared.repositories.wallet_repository import WalletRepository
from shared.databases.mongo_client import MongoConnection
from config import RedisConfig
import redis
from shared.repositories.portfolio_repository import PortfolioRepository


class WalletService:

    def __init__(self):
        db = MongoConnection.get_database()
        self.db = db
        self.wallet_repository = WalletRepository(db)
        self.portfolio_repository = PortfolioRepository(db)
        self.redis_client = redis.from_url(RedisConfig.CONNECTION_URL)

    async def add_wallet(self, wallet: str):
        wallet_clean = wallet.lower().strip()

        self.wallet_repository.queue_wallet(wallet_clean)

        event_id = self.redis_client.xadd(
            RedisConfig.PORTFOLIO_STREAM,
            {"wallet": wallet_clean, "action": "CRAWL_NEW_USER"},
            id="*"
        )

        return {
            "success": True,
            "wallet": wallet_clean,
            "status": "queued",
            "msg": "Wallet added to crawl queue successfully",
            "event_id": event_id.decode() if isinstance(event_id, bytes) else event_id
        }

    async def get_wallet_status(self, wallet: str):
        wallet_clean = wallet.lower().strip()
        self.wallet_repository.recover_stale_syncing()
        row = self.wallet_repository.get_wallet(wallet_clean)
        latest = self.portfolio_repository.get_latest_snapshot(wallet_clean)
        status = (row or {}).get("status")

        if latest and status != "syncing":
            status = "synced"
        elif status in ("queued", "syncing"):
            status = status
        elif row:
            status = status or "queued"
        else:
            status = "guest"

        return {
            "wallet": wallet_clean,
            "status": status,
            "isTracked": status == "synced",
            "canUseFullFeatures": status == "synced",
            "hasSnapshot": bool(latest),
            "lastSyncedAt": latest.get("timestamp") if latest else None,
            "syncError": (row or {}).get("sync_error"),
            "message": self._status_message(status),
        }

    async def get_wallets(self):
        wallets = self.wallet_repository.get_active_wallets()
        return {"count": len(wallets), "wallets": wallets}

    def _status_message(self, status: str) -> str:
        return {
            "guest": "Wallet is connected locally only. Update Plus is required to crawl portfolio data.",
            "queued": "Wallet is queued for initial crawl. This can take a few minutes.",
            "syncing": "Wallet crawl is running.",
            "synced": "Wallet is tracked and full portfolio features are available.",
            "failed": "Wallet crawl failed. You can retry Update Plus or run the sync worker again.",
            "disabled": "Wallet tracking is disabled.",
        }.get(status, "Wallet status is unknown.")
