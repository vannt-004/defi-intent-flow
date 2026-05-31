from routers.user_router import router as user_router
from routers.yield_router import router as yield_router
from routers.token_router import router as token_router
from routers.portfolio_analytics_router import router as portfolio_analytics_router
from routers.simulation_router import router as simulation_router

routers = [
    portfolio_analytics_router,
    user_router,
    yield_router,
    token_router,
    simulation_router,
]
