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
def approve_proposal(
    proposal_id: int,
    engine: Engine = Depends(get_sync_engine),
):
    """제안 승인 → PROPOSED_LINK를 DISCOVERED_LINK로 전환.

    1. PG: status → 'approved'
    2. Neo4j: PROPOSED_LINK 삭제 → DISCOVERED_LINK 생성
    """
    import json
    from sqlalchemy import text as sa_text

    with engine.connect() as conn:
        # 제안 조회
        row = conn.execute(
            sa_text("SELECT * FROM relationship_proposals WHERE id = :id"),
            {"id": proposal_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if row["status"] != "proposed":
            raise HTTPException(status_code=400, detail=f"Cannot approve: status={row['status']}")

        # PG status 변경
        conn.execute(
            sa_text("UPDATE relationship_proposals SET status='approved', approved_at=NOW() WHERE id = :id"),
            {"id": proposal_id},
        )
        conn.commit()

    # Neo4j: PROPOSED_LINK → DISCOVERED_LINK 승격
    # 1. 기존 PROPOSED_LINK 삭제 (제안 상태 관계 제거)
    # 2. Attribute 노드를 MERGE로 보장 + DISCOVERED_LINK 생성 (승인 상태 관계 생성)
    #
    # "비건", "무기자차" 등은 기존 Neo4j 노드(Ingredient, Brand)가 아니라
    # 속성값이므로, Attribute 노드를 동적 생성하여 관계를 연결한다.
    evidence = row["evidence"] if isinstance(row["evidence"], str) else json.dumps(row["evidence"], ensure_ascii=False)
    with neo4j_driver.session() as session:
        session.run(
            "MATCH ()-[r:PROPOSED_LINK {proposalId: $pid}]->() DELETE r",
            pid=proposal_id,
        )
        session.run(
            """
            MERGE (s:Attribute {name: $source})
            MERGE (t:Attribute {name: $target})
            MERGE (s)-[new:DISCOVERED_LINK {proposalId: $pid}]->(t)
            SET new.type = $rtype,
                new.evidence = $evidence,
                new.source = 'pattern_scout'
            """,
            source=row["source_concept"],
            target=row["target_concept"],
            pid=proposal_id,
            rtype=row["relationship_type"],
            evidence=evidence,
        )

    return {"status": "approved", "proposal_id": proposal_id}


@router.post("/knowledge/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    reason: str = "",
    engine: Engine = Depends(get_sync_engine),
):
    """제안 거부 → PROPOSED_LINK 삭제."""
    from sqlalchemy import text as sa_text

    with engine.connect() as conn:
        row = conn.execute(
            sa_text("SELECT status FROM relationship_proposals WHERE id = :id"),
            {"id": proposal_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")

        conn.execute(
            sa_text("UPDATE relationship_proposals SET status='rejected', rejected_at=NOW(), rejection_reason=:reason WHERE id = :id"),
            {"id": proposal_id, "reason": reason},
        )
        conn.commit()

    # Neo4j: PROPOSED_LINK 삭제
    with neo4j_driver.session() as session:
        session.run(
            "MATCH ()-[r:PROPOSED_LINK {proposalId: $pid}]->() DELETE r",
            pid=proposal_id,
        )

    return {"status": "rejected", "proposal_id": proposal_id}
