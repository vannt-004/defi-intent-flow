from fastapi import APIRouter

from data_engine.services.yields.yield_service import YieldService

router = APIRouter(prefix="/yields", tags=["Yield"])

service = YieldService()


@router.get("/")
async def get_yields(profile: str = "balanced", limit: int = 100):
    return service.get_ranked_markets(profile_or_matrix=profile, limit=limit)

