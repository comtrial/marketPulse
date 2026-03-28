from fastapi import APIRouter
from sqlalchemy import text

from core.database import async_session
from core.neo4j_client import verify_neo4j_connection

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    checks = {"postgres": False, "neo4j": False}

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            checks["postgres"] = True
    except Exception:
        pass

    checks["neo4j"] = verify_neo4j_connection()

    status = "healthy" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}
