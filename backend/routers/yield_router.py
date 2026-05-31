from fastapi import APIRouter, Query

from data_engine.services.yields.yield_service import YieldService

router = APIRouter(prefix="/yields", tags=["Yield"])

service = YieldService()


@router.get("/")
async def get_yields(
    profile: str = "balanced",
    limit: int = 100,
    yield_weight: float | None = Query(default=None, ge=0.01, le=1),
    safety_weight: float | None = Query(default=None, ge=0.01, le=1),
    efficiency_weight: float | None = Query(default=None, ge=0.01, le=1),
):
    weights = None
    if yield_weight is not None and safety_weight is not None and efficiency_weight is not None:
        weights = {
            "yield": yield_weight,
            "safety": safety_weight,
            "efficiency": efficiency_weight,
        }

    return service.get_ranked_markets(profile_or_matrix=weights or profile, limit=limit)
