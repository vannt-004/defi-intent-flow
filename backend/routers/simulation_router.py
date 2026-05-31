from fastapi import APIRouter

from portfolio_engine.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulation", tags=["Simulation"])


@router.post("/{wallet}")
async def simulate_wallet(wallet: str, payload: dict):
    service = SimulationService()
    return service.simulate(wallet, payload)


@router.post("/intent/parse")
async def parse_simulation_intent(payload: dict):
    service = SimulationService()
    return service.parse_intent(payload.get("text") or "")
