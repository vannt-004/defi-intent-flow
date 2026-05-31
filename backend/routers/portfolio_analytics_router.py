from fastapi import APIRouter, Query

from data_engine.services.user.onchain_transaction_crawler import OnchainTransactionCrawler
from portfolio_engine.services.portfolio_analytics_service import PortfolioAnalyticsService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.onchain_transaction_repository import OnchainTransactionRepository

router = APIRouter(prefix="/portfolio/analytics", tags=["Portfolio Analytics"])


@router.get("/{wallet}")
async def get_portfolio_analytics(wallet: str):
    service = PortfolioAnalyticsService()
    return service.get_dashboard(wallet)


@router.get("/{wallet}/transactions")
async def get_portfolio_transactions(wallet: str, limit: int = Query(default=100, ge=1, le=500)):
    service = PortfolioAnalyticsService()
    return service.get_transactions(wallet, limit=limit)


@router.get("/{wallet}/positions-pnl")
async def get_portfolio_positions_pnl(wallet: str):
    service = PortfolioAnalyticsService()
    return service.get_positions_pnl(wallet)


@router.get("/{wallet}/history")
async def get_portfolio_history(wallet: str, limit: int = Query(default=90, ge=1, le=1000)):
    service = PortfolioAnalyticsService()
    return service.get_chart_history(wallet, limit=limit)


@router.get("/{wallet}/onchain-transactions")
async def get_onchain_transactions(wallet: str, limit: int = Query(default=100, ge=1, le=500)):
    db = MongoConnection.get_database()
    repository = OnchainTransactionRepository(db)
    return repository.get_wallet_transactions(wallet.lower(), limit=limit)


@router.post("/{wallet}/crawl-onchain")
async def crawl_onchain_transactions(
    wallet: str,
    start_block: int | None = None,
    end_block: int = Query(default=99999999, ge=0),
):
    crawler = OnchainTransactionCrawler()
    try:
        return await crawler.crawl_wallet(wallet=wallet, start_block=start_block, end_block=end_block)
    finally:
        await crawler.close()
