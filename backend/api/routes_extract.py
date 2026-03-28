"""속성 추출 API 엔드포인트.

POST /api/v1/extract       — 단건 추출 (데모 UI용, graph_sync 없음)
POST /api/v1/extract/batch — 배치 추출 (주문 일괄 처리, graph_sync 포함)
GET  /api/v1/extract/stats — 추출 통계

배치 추출 흐름:
  1. orders_unified에서 아직 추출 안 된 주문 조회
  2. 각 주문마다:
     a. extractor.extract(product_name, order_context)
        → 벡터 검색 → LLM 1회 → 검증 → graph_sync (validation 통과 시)
     b. extractions 테이블에 결과 저장
  3. 초당 5건 rate limit (Anthropic API 보호)
"""

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from extraction.extractor import CosmeticExtractor
from extraction.graph_sync import OrderContext
from models.schemas import (
    BatchExtractRequest,
    BatchExtractResponse,
    ExtractRequest,
    ExtractResponse,
    ExtractStatsResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["extract"])

# ── 싱글톤 의존성 ──

_extractor: CosmeticExtractor | None = None


def get_extractor() -> CosmeticExtractor:
    """Extractor 싱글톤. main.py lifespan에서 init_extractor()로 초기화."""
    if _extractor is None:
        raise RuntimeError("Extractor not initialized. Call init_extractor() first.")
    return _extractor


def init_extractor(extractor: CosmeticExtractor) -> None:
    """main.py lifespan에서 호출하여 싱글톤 등록."""
    global _extractor
    _extractor = extractor


# ── 엔드포인트 ──


@router.post("/extract", response_model=ExtractResponse)
async def extract_single(
    req: ExtractRequest,
    extractor: CosmeticExtractor = Depends(get_extractor),
):
    """단건 추출 — 상품명 하나를 받아서 속성 추출 결과 반환.

    order=None 명시: 주문 컨텍스트 없이 호출하므로 graph_sync는 수행되지 않음.
    데모 UI에서 실시간으로 추출 결과를 확인할 때 사용.
    """
    result = await extractor.extract(
        product_text=req.product_name,
        order=None,  # 단건 추출 — graph_sync 의도적으로 수행 안 함
    )

    return ExtractResponse(
        attributes=result.attributes,
        validation_passed=result.validation.passed,
        errors=result.validation.errors,
        warnings=result.validation.warnings,
        examples_used=result.examples_used,
        avg_similarity=result.avg_similarity,
        cost_usd=result.cost.cost_usd,
        latency_ms=result.cost.latency_ms,
        graph_synced=result.graph_synced,
    )


@router.post("/extract/batch", response_model=BatchExtractResponse)
async def extract_batch(
    req: BatchExtractRequest,
    extractor: CosmeticExtractor = Depends(get_extractor),
    db: AsyncSession = Depends(get_db),
):
    """배치 추출 — 아직 추출되지 않은 주문을 일괄 처리.

    extractions 테이블에 이미 있는 order_id는 건너뜀.
    각 건마다 LLM 추출 → 검증 → graph_sync(통과 시) → DB 저장.
    """
    # 아직 추출 안 된 주문 조회
    platform_filter = ""
    params: dict = {"limit": req.limit}
    if req.platform:
        platform_filter = "AND u.platform = :platform"
        params["platform"] = req.platform

    result = await db.execute(
        text(f"""
            SELECT u.order_id, u.order_date, u.platform, u.destination_country,
                   u.brand, u.product_name, u.product_type, u.quantity, u.unit_price_usd
            FROM orders_unified u
            WHERE u.order_id NOT IN (SELECT order_id FROM extractions)
            {platform_filter}
            ORDER BY u.order_date
            LIMIT :limit
        """),
        params,
    )
    orders = result.mappings().all()

    succeeded = 0
    failed = 0
    total_cost = 0.0

    for i, order in enumerate(orders):
        try:
            # 주문 데이터에서 온 컨텍스트 (country, platform, product_type)
            order_ctx = OrderContext(
                order_id=order["order_id"],
                product_name=order["product_name"],
                product_type=order["product_type"],
                destination_country=order["destination_country"],
                platform=order["platform"],
            )

            # 추출 실행 — 벡터 검색 → LLM → 검증 → graph_sync
            ext_result = await extractor.extract(
                product_text=order["product_name"],
                order=order_ctx,  # 배치 — graph_sync 수행 (validation 통과 시)
            )

            # extractions 테이블에 저장
            await db.execute(
                text("""
                    INSERT INTO extractions
                        (extraction_id, order_id, platform, attributes,
                         avg_similarity, examples_used,
                         input_tokens, output_tokens, cost_usd, latency_ms,
                         validation_passed, validation_warnings,
                         graph_synced)
                    VALUES
                        (:eid, :oid, :platform, :attrs,
                         :sim, :examples,
                         :in_tok, :out_tok, :cost, :latency,
                         :passed, :warnings,
                         :synced)
                """),
                {
                    "eid": str(uuid.uuid4()),
                    "oid": order["order_id"],
                    "platform": order["platform"],
                    "attrs": json.dumps(ext_result.attributes, ensure_ascii=False),
                    "sim": ext_result.avg_similarity,
                    "examples": ext_result.examples_used,
                    "in_tok": ext_result.cost.input_tokens,
                    "out_tok": ext_result.cost.output_tokens,
                    "cost": ext_result.cost.cost_usd,
                    "latency": ext_result.cost.latency_ms,
                    "passed": ext_result.validation.passed,
                    "warnings": ext_result.validation.warnings or None,
                    "synced": ext_result.graph_synced,
                },
            )
            await db.commit()

            total_cost += ext_result.cost.cost_usd
            succeeded += 1

        except Exception as e:
            failed += 1
            logger.error(
                "batch_extraction_failed",
                order_id=order["order_id"],
                error=str(e),
            )

        # Rate limit: Anthropic API 보호 — 초당 5건
        if (i + 1) % 5 == 0:
            await asyncio.sleep(1.0)

    return BatchExtractResponse(
        total=len(orders),
        succeeded=succeeded,
        failed=failed,
        total_cost_usd=round(total_cost, 6),
    )


@router.get("/extract/stats", response_model=ExtractStatsResponse)
async def extract_stats(db: AsyncSession = Depends(get_db)):
    """추출 통계 — 총 건수, 비용, graph_sync 비율, error 비율."""
    result = await db.execute(
        text("""
            SELECT
                count(*) AS total,
                coalesce(sum(cost_usd), 0) AS total_cost,
                count(*) FILTER (WHERE graph_synced = true) AS synced,
                count(*) FILTER (WHERE validation_passed = false) AS errors,
                coalesce(avg(latency_ms), 0) AS avg_latency
            FROM extractions
        """)
    )
    row = result.mappings().one()
    total = row["total"] or 0

    return ExtractStatsResponse(
        total_extractions=total,
        total_cost_usd=float(row["total_cost"]),
        graph_synced_count=row["synced"],
        graph_synced_ratio=row["synced"] / total if total > 0 else 0.0,
        error_count=row["errors"],
        error_ratio=row["errors"] / total if total > 0 else 0.0,
        avg_latency_ms=float(row["avg_latency"]),
    )
