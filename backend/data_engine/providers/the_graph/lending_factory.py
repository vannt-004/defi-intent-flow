from data_engine.providers.the_graph.sub.compound_service import CompoundGraph
from data_engine.services.prices.pricing_service import PricingService
from data_engine.providers.the_graph.sub.aave_service import AaveGraph

class LendingProviderFactory:
    def __init__(self, pricing: PricingService):
        self.providers = [
            AaveGraph(pricing),
            CompoundGraph(pricing)
        ]

    def get_all_providers(self):
        return self.providers