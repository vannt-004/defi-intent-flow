# data_engine/workers/yield_worker.py
from data_engine.providers.the_graph.lending_factory import LendingProviderFactory
from data_engine.providers.the_graph.sub.uniswap_service import UniswapGraph
from data_engine.services.prices.pricing_service import PricingService
from data_engine.workers.base_worker import BaseWorker
from shared.databases.mongo_client import MongoConnection
from shared.repositories.config_repository import ConfigRepository
from shared.repositories.yield_repository import YieldRepository


class YieldWorker(BaseWorker):
    def __init__(self, scheduler: str = "^true@3600"):
        super().__init__(name="YieldWorker", scheduler=scheduler)

        db = MongoConnection.get_database()

        self.yield_repository = YieldRepository(db)
        self.config_repository = ConfigRepository(db)
        self.pricing = PricingService(db)

        self.lending_factory = LendingProviderFactory(self.pricing)
        self.uniswap_service = UniswapGraph(self.pricing)

        self.batch_size = 1000
        self.min_tvl = 10_000

    async def process(self):
        self.logger.info("[YieldWorker] Aggregating raw protocol markets...")
        all_markets = []

        for provider in self.lending_factory.get_all_providers():
            provider_name = provider.__class__.__name__
            try:
                markets = await provider.get_markets(min_tvl=self.min_tvl)
                if markets:
                    all_markets.extend(markets)
            except Exception as e:
                self.logger.error(
                    f"[YieldWorker] Failed to fetch markets from {provider_name}: {e}"
                    )

        try:
            uniswap_pools = await self.uniswap_service.get_pools(
                batch_size=self.batch_size, min_tvl=self.min_tvl
            )
            if uniswap_pools:
                all_markets.extend(uniswap_pools)
        except Exception as e:
            self.logger.error(f"[YieldWorker] Failed to fetch pools from Uniswap: {e}")

        if not all_markets:
            self.logger.warning("[YieldWorker] No markets fetched from any provider.")
            self.config_repository.save_cursor("yield_worker", "empty")
            return

        try:
            result = self.yield_repository.bulk_upsert(all_markets)

            self.logger.info(
                f"[YieldWorker] Successfully cached {len(all_markets)} raw markets into DB."
                )
            self.config_repository.save_cursor(
                "yield_worker",
                f"cached_{len(all_markets)}"
                )
        except Exception as e:
            self.logger.error(
                f"[YieldWorker] Bulk upsert to YieldRepository failed: {e}"
                )