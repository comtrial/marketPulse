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

    # Extractor 초기화 (벡터 스토어 + graph_syncer)
    from api.routes_extract import init_extractor
    from extraction.cost_tracker import CostTracker
    from extraction.extractor import CosmeticExtractor
    from extraction.graph_sync import GraphSynchronizer
    from extraction.validator import ExtractionValidator
    from extraction.vector_store import VectorStore

    vector_store = VectorStore(persist_dir=settings.chroma_persist_dir)
    graph_syncer = GraphSynchronizer(driver=neo4j_driver)

    extractor = CosmeticExtractor(
        vector_store=vector_store,
        validator=ExtractionValidator(),
        cost_tracker=CostTracker(),
        graph_syncer=graph_syncer,
    )
    init_extractor(extractor)

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
    from api.routes_extract import router as extract_router

    app.include_router(health_router)
    app.include_router(extract_router)

    return app
