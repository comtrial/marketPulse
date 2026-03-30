"""Action 도구 서버 — PatternScout가 관계를 제안하고 인사이트를 저장.

propose_relationship: 통계적 패턴을 관계로 제안 (PG + Neo4j PROPOSED_LINK)
save_market_insight: 발견한 인사이트를 DB에 저장

Stage→Review→Approve 패턴 (Palantir 참조):
  LLM이 제안 (propose) → 사람이 승인 (approve API) → Neo4j에 DISCOVERED_LINK 편입
  자동 승인하지 않음 — human-in-the-loop.
"""

import json

import structlog
from neo4j import Driver
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from orchestrator.tool_decorator import tool

logger = structlog.get_logger()


# ── 입력 스키마 ──


class ProposeRelationshipInput(BaseModel):
    source_concept: str = Field(description="소스 개념 (예: 비건)")
    target_concept: str = Field(description="타겟 개념 (예: 무기자차)")
    relationship_type: str = Field(description="관계 유형: SYNERGY | TEMPORAL_CORRELATION | CROSS_MARKET_GAP")
    evidence: dict = Field(description="코드가 계산한 통계적 근거 (lift, correlation 등)")
    reasoning: str = Field(description="LLM의 해석 — 왜 이 관계가 의미 있는지")


class SaveMarketInsightInput(BaseModel):
    type: str = Field(description="인사이트 유형: trend | gap | opportunity")
    country: str = Field(description="국가 코드")
    product_type: str = Field(description="제품 유형")
    summary: str = Field(description="인사이트 요약")
    evidence: dict = Field(description="근거 데이터")
    trace_id: str = Field(description="관련 trace ID")


# ── 서버 ──


class ActionServer:
    """PatternScout 전용 쓰기 도구. AnalystAgent는 이 도구를 사용하지 않는다."""

    def __init__(self, engine: Engine, neo4j_driver: Driver):
        self.engine = engine
        self.neo4j_driver = neo4j_driver

    @tool(ProposeRelationshipInput)
    def propose_relationship(self, params: ProposeRelationshipInput) -> dict:
        """통계적 패턴을 관계로 제안. 자동 승인하지 않음 — 사람이 대시보드에서 승인.

        동작:
          1. relationship_proposals 테이블에 INSERT (status='proposed')
          2. Neo4j에 PROPOSED_LINK 생성 (시각화 + 승인 시 DISCOVERED_LINK로 전환)
          3. 이미 같은 소스→타겟 제안이 있으면 중복 반환
        """
        # 중복 체크
        with self.engine.connect() as conn:
            existing = conn.execute(
                text("""
                    SELECT id FROM relationship_proposals
                    WHERE source_concept = :s AND target_concept = :t AND status != 'rejected'
                """),
                {"s": params.source_concept, "t": params.target_concept},
            ).mappings().first()

            if existing:
                return {"status": "duplicate", "existing_id": existing["id"]}

            # PG INSERT
            result = conn.execute(
                text("""
                    INSERT INTO relationship_proposals
                        (source_concept, target_concept, relationship_type,
                         evidence, reasoning, status)
                    VALUES (:s, :t, :rt, CAST(:ev AS jsonb), :reason, 'proposed')
                    RETURNING id
                """),
                {
                    "s": params.source_concept,
                    "t": params.target_concept,
                    "rt": params.relationship_type,
                    "ev": json.dumps(params.evidence, ensure_ascii=False),
                    "reason": params.reasoning,
                },
            )
            proposal_id = result.scalar()
            conn.commit()

        # Neo4j PROPOSED_LINK
        # "비건", "무기자차" 등은 기존 노드(Ingredient, Brand 등)가 아니라
        # 속성값(valueClaims, additionalAttrs)이므로 Neo4j에 노드가 없을 수 있다.
        # → Attribute 노드를 MERGE로 동적 생성하여 관계를 연결한다.
        with self.neo4j_driver.session() as session:
            session.run(
                """
                MERGE (s:Attribute {name: $source})
                MERGE (t:Attribute {name: $target})
                MERGE (s)-[r:PROPOSED_LINK {proposalId: $pid}]->(t)
                SET r.type = $rtype,
                    r.evidence = $evidence,
                    r.status = 'proposed'
                """,
                source=params.source_concept,
                target=params.target_concept,
                pid=proposal_id,
                rtype=params.relationship_type,
                evidence=json.dumps(params.evidence, ensure_ascii=False),
            )

        logger.info(
            "relationship_proposed",
            id=proposal_id,
            source=params.source_concept,
            target=params.target_concept,
            type=params.relationship_type,
        )
        return {"status": "proposed", "proposal_id": proposal_id}

    @tool(SaveMarketInsightInput)
    def save_market_insight(self, params: SaveMarketInsightInput) -> dict:
        """발견한 인사이트를 DB에 저장."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO market_insights
                        (type, country, product_type, summary, evidence, trace_id)
                    VALUES (:type, :country, :ptype, :summary, CAST(:ev AS jsonb), :tid)
                    RETURNING id
                """),
                {
                    "type": params.type,
                    "country": params.country,
                    "ptype": params.product_type,
                    "summary": params.summary,
                    "ev": json.dumps(params.evidence, ensure_ascii=False),
                    "tid": params.trace_id,
                },
            )
            insight_id = result.scalar()
            conn.commit()

        logger.info("market_insight_saved", id=insight_id, type=params.type)
        return {"status": "saved", "insight_id": insight_id}
