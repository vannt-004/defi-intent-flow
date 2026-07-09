from fastapi import APIRouter, Query

from portfolio_engine.services.portfolio_analytics_service import PortfolioAnalyticsService
from portfolio_engine.services.portfolio_service import PortfolioService
from portfolio_engine.services.position_risk_service import PositionRiskService


router = APIRouter(prefix="/portfolio/analytics", tags=["Portfolio Analytics"])


@router.get("/{wallet}")
async def get_portfolio_analytics(wallet: str):
    service = PortfolioAnalyticsService()
    return service.get_dashboard(wallet)


@router.get("/{wallet}/preview")
async def get_portfolio_preview_analytics(wallet: str):
    service = PortfolioService(wallet)
    return await service.get_preview_analytics()


@router.get("/{wallet}/transactions")
async def get_portfolio_transactions(wallet: str, limit: int = Query(default=100, ge=1, le=500)):
    service = PortfolioAnalyticsService()
    return service.get_transactions(wallet, limit=limit)


@router.get("/{wallet}/positions-pnl")
async def get_portfolio_positions_pnl(wallet: str):
    service = PortfolioAnalyticsService()
    return service.get_positions_pnl(wallet)


@router.get("/{wallet}/pnl-flows")
async def get_portfolio_pnl_flows(wallet: str, limit: int = Query(default=30, ge=1, le=200)):
    service = PortfolioAnalyticsService()
    return service.get_pnl_flows(wallet, limit=limit)


@router.get("/{wallet}/history")
async def get_portfolio_history(wallet: str, limit: int = Query(default=90, ge=1, le=1000)):
    service = PortfolioAnalyticsService()
    return service.get_chart_history(wallet, limit=limit)


@router.get("/{wallet}/risk")
async def get_portfolio_position_risk(wallet: str):
    service = PositionRiskService()
    return service.get_wallet_risk(wallet)


@router.get("/{wallet}/risk/history")
async def get_portfolio_risk_history(wallet: str, limit: int = Query(default=90, ge=1, le=1000)):
    service = PositionRiskService()
    return service.get_portfolio_risk_history(wallet, limit=limit)
