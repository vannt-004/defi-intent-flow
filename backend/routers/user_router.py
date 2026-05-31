from fastapi import APIRouter

from data_engine.models.wallet_model import AddWalletRequest
from data_engine.services.wallet_service import WalletService
from portfolio_engine.services.portfolio_service import PortfolioService
from portfolio_engine.services.position_service import PositionService

router = APIRouter(prefix="/portfolio", tags=["Portfolio"], )

service = PositionService()

wallet_service = WalletService()


@router.post("/wallet")
async def add_wallet(body: AddWalletRequest):
    return await wallet_service.add_wallet(body.wallet)


@router.get("/wallet/{wallet}/status")
async def get_wallet_status(wallet: str):
    return await wallet_service.get_wallet_status(wallet)


@router.get("/{wallet}")
async def get_overview_portfolio(wallet: str):
    portfolio_service = PortfolioService(wallet)

    return await portfolio_service.get_data()


@router.get("/positions/{wallet}")
async def get_positions(wallet: str):
    return await service.get_positions(wallet)
