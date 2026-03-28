from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from core.config import settings
from core.database import engine
from core.neo4j_client import neo4j_driver

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_up", env=settings.env)
    yield
    await engine.dispose()
    neo4j_driver.close()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MarketPulse",
        description="Cross-Border Ecommerce Intelligence — Beauty & Cosmetics",
        version="0.1.0",
        lifespan=lifespan,
    )

    from api.routes_health import router as health_router

    app.include_router(health_router)

    return app
