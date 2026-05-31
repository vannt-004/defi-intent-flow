from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from routers import routers


def create_app() -> FastAPI:

    app = FastAPI(
        title="DeFi Portfolio API",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in routers:
        app.include_router(router)

    return app