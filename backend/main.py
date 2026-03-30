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

    # Intelligence 레이어 초기화 (MCP 서버 + 오케스트레이터)
    from sqlalchemy import create_engine

    from api.routes_intelligence import init_order_server
    from api.routes_kg import init_kg_server
    from api.routes_orchestrator import init_orchestrator
    from mcp_servers.kg_server import KnowledgeGraphServer
    from mcp_servers.order_server import OrderDataServer
    from orchestrator.llm_orchestrator import LLMOrchestrator
    from orchestrator.trace_logger import TraceLogger

    sync_engine = create_engine(settings.database_url_sync)

    kg_server = KnowledgeGraphServer(driver=neo4j_driver)
    order_server = OrderDataServer(engine=sync_engine)
    trace_logger = TraceLogger(engine=sync_engine, tool_to_server={})

    orchestrator = LLMOrchestrator(
        kg_server=kg_server,
        order_server=order_server,
        trace_logger=trace_logger,
    )

    init_kg_server(kg_server)
    init_order_server(order_server)
    init_orchestrator(orchestrator, trace_logger)

    yield
    await engine.dispose()
    neo4j_driver.close()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="MarketPulse",
        description="Cross-Border Ecommerce Intelligence — Beauty & Cosmetics",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes_health import router as health_router
    from api.routes_extract import router as extract_router
    from api.routes_intelligence import router as intelligence_router
    from api.routes_orchestrator import router as orchestrator_router
    from api.routes_kg import router as kg_router
    from api.routes_eval import router as eval_router

    app.include_router(health_router)
    app.include_router(extract_router)
    app.include_router(intelligence_router)
    app.include_router(orchestrator_router)
    app.include_router(kg_router)
    app.include_router(eval_router)

    return app
