from data_engine.providers.the_graph.lending_factory import LendingProviderFactory
from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection

from data_engine.providers.the_graph.sub.uniswap_service import UniswapGraph


class PositionService:
    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)

        self.lending_factory = LendingProviderFactory(self.pricing)

        self.uniswap = UniswapGraph(self.pricing)

    async def get_positions(self, wallet: str) -> list:
        wallet = wallet.lower().strip()
        all_positions = []

        for provider in self.lending_factory.get_all_providers():
            try:
                lending_positions = await provider.get_positions(wallet)
                if lending_positions:
                    all_positions.extend(lending_positions)
            except Exception as e:
                print(f"[PositionService] Error fetching positions from {provider.__class__.__name__}: {e}")

        try:
            if hasattr(self.uniswap, "get_positions"):
                uni_positions = await self.uniswap.get_positions(wallet)
                all_positions.extend(uni_positions)
        except Exception as e:
            print(f"[PositionService] Error fetching Uniswap positions: {e}")

        return all_positions
