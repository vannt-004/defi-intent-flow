import json
import redis.asyncio as redis
from config import RedisConfig
from data_engine.workers.base_worker import BaseWorker
from shared.databases.mongo_client import MongoConnection
from shared.repositories.wallet_repository import WalletRepository


class PortfolioAnalyticsWorker(BaseWorker):

    def __init__(self, scheduler: str = "^true@1800"):
        super().__init__(name="PortfolioAnalyticsWorker", scheduler=scheduler)

        db = MongoConnection.get_database()
        self.wallet_repository = WalletRepository(db)

        self.redis = redis.from_url(RedisConfig.CONNECTION_URL, decode_responses=True)

    async def process(self):
        wallets = self.wallet_repository.get_active_wallets(limit=5000)

        if not wallets:
            self.logger.info("No active wallets found to sync.")
            return

        self.logger.info(f"Found {len(wallets)} active wallets. Pushing to queue...")

        for wallet in wallets:
            wallet = wallet.lower().strip()
            try:
                event_data = {"wallet": wallet}
                await self.redis.xadd(
                    name=RedisConfig.PORTFOLIO_STREAM,
                    fields={"msg": json.dumps(event_data)},
                    id="*"
                )
            except Exception as e:
                self.logger.error(f"Failed to push wallet={wallet} to stream. Error={e}")

        self.logger.info("Finished pushing all wallet sync events to Redis Stream.")
