import asyncio

from data_engine.providers.coingekco.coingekco import CoinGecko
from data_engine.services.prices.price_sync_service import PriceSyncService
from data_engine.workers.base_worker import BaseWorker
from shared.databases.mongo_client import MongoConnection
from shared.repositories.price_snapshot_repository import PriceSnapshotRepository
from shared.repositories.token_repository import TokenRepository


class PriceWorker(BaseWorker):

    def __init__(self, scheduler: str = "^true@15"):
        super().__init__(name="PriceWorker", scheduler=scheduler)

        db = MongoConnection.get_database()
        self.token_repository = TokenRepository(db)
        self.snapshot_repository = PriceSnapshotRepository(db)

        self.coingecko_service = CoinGecko()

        self.sync_service = PriceSyncService(
            token_repository=self.token_repository,
            snapshot_repository=self.snapshot_repository,
            coingecko_service=self.coingecko_service,
        )

    async def process(self):

        await asyncio.gather(
            self.sync_service.sync_prices(),
            # self.sync_service.sync_metadata()
        )

    async def stop(self):
        await super().stop()
        await self.coingecko_service.close()