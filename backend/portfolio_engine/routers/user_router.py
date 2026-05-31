

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio"]
)

@router.get("/positions/{wallet}")
async def get_portfolio(wallet: str, service: PortfolioService = Depends(get_portfolio_service)):
    return await service.get_portfolio(wallet)

@router.get("/wallet/{wallet}")
async def get_portfolio(wallet: str, service: PortfolioService = Depends(get_portfolio_service)):
    return await service.get_wallet(wallet)