from data_engine.workers.portfolio_worker import PortfolioAnalyticsWorker
from data_engine.workers.price_worker import PriceWorker
from data_engine.workers.yield_worker import YieldWorker

workers = [
    PriceWorker(scheduler="^true@60"),
    YieldWorker(scheduler="^true@360"),
    PortfolioAnalyticsWorker(scheduler="^true@360")
]