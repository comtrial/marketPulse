"""Eval + Knowledge API 엔드포인트.

4축 Eval 메트릭 조회 + Knowledge 제안 관리.
PatternScout 미구현 시에도 동작 (0/빈값 반환).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from core.config import settings
from core.neo4j_client import neo4j_driver
from eval.metrics import (
    eval_answer_quality,
    eval_pattern_discovery,
    eval_reasoning_coverage,
    eval_system_efficiency,
    find_before_after_pairs,
    run_full_eval,
)
from eval.snapshots import compare_snapshots, save_snapshot

router = APIRouter(prefix="/api/v1", tags=["eval"])

_sync_engine: Engine | None = None


def get_sync_engine() -> Engine:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.database_url_sync)
    return _sync_engine


# ── Eval 메트릭 ──


@router.get("/eval/pattern-discovery")
def get_pattern_discovery(engine: Engine = Depends(get_sync_engine)):
    """축 1: PatternScout 패턴 탐지 현황."""
    return eval_pattern_discovery(engine, neo4j_driver)


@router.get("/eval/answer-quality")
def get_answer_quality(engine: Engine = Depends(get_sync_engine)):
    """축 2: 답변 품질 개선률 (discovered_usage_rate)."""
    return eval_answer_quality(engine)


@router.get("/eval/reasoning-coverage")
def get_reasoning_coverage(engine: Engine = Depends(get_sync_engine)):
    """축 3: 추론 커버리지 (국가×유형 매트��스)."""
    return eval_reasoning_coverage(engine, neo4j_driver)


@router.get("/eval/system-efficiency")
def get_system_efficiency(engine: Engine = Depends(get_sync_engine)):
    """축 4: 시스템 효율 (세션별 비용 변화)."""
    return eval_system_efficiency(engine)


@router.get("/eval/before-after-pairs")
def get_before_after_pairs(engine: Engine = Depends(get_sync_engine)):
    """Before/After 답변 비교 쌍."""
    return find_before_after_pairs(engine)


@router.get("/eval/full")
def get_full_eval(engine: Engine = Depends(get_sync_engine)):
    """4축 통합 + before_after_pairs."""
    return run_full_eval(engine, neo4j_driver)


# ── 스냅샷 ──


@router.post("/eval/snapshot/{name}")
def create_snapshot(name: str, engine: Engine = Depends(get_sync_engine)):
    """현재 시점의 Eval 스냅샷 저장."""
    return save_snapshot(engine, neo4j_driver, name=name)


@router.get("/eval/compare")
def get_compare(before: str, after: str):
    """두 스냅샷 비교. ?before=before_pattern_scout&after=after_pattern_scout"""
    return compare_snapshots(before_name=before, after_name=after)


# ── Knowledge Proposals (Step 5에서 구현) ──


@router.get("/knowledge/proposals")
def list_proposals(engine: Engine = Depends(get_sync_engine)):
    """제안된 관계 목록. relationship_proposals 테이블이 없으면 빈 리스트."""
    from eval.metrics import _table_exists

    if not _table_exists(engine, "relationship_proposals"):
        return []

    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM relationship_proposals ORDER BY created_at DESC")
        ).mappings().all()
        return [dict(r) for r in rows]


@router.post("/knowledge/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int):
    """제안 승인. Step 5에서 구현."""
    raise HTTPException(status_code=501, detail="PatternScout Phase 2에서 구현 예정")


@router.post("/knowledge/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int):
    """제안 거부. Step 5에서 구현."""
    raise HTTPException(status_code=501, detail="PatternScout Phase 2에서 구현 예정")
