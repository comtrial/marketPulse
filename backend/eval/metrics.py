"""4축 Eval 메트릭 + Before/After 답변 비교.

PatternScout가 없어도 동작한다 — 전부 0/빈값을 반환.
PatternScout가 들어오면 코드 변경 없이 수치가 채워진다.

축 1: 패턴 탐지 현황   — relationship_proposals 테이블 집계
축 2: 답변 품질 개선률  — orchestrator_results에서 discovered_links 활용 여부
축 3: 추론 커버리지     — 국가×유형 매트릭스 (Neo4j/PG에서 동적으로 조회)
축 4: 시스템 효율       — 세션별 비용 변화

상수 하드코딩 없음 — 국가/유형 목록을 Neo4j에서 가져와서 사용.
시드 데이터가 바뀌어도 코드 수정 불필요.
"""

import json

import structlog
from neo4j import Driver
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = structlog.get_logger()


# ── 헬퍼 ──────────────────────────────────────────────────


def _table_exists(engine: Engine, table_name: str) -> bool:
    """PostgreSQL에 테이블이 존재하는지 확인."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
            ),
            {"t": table_name},
        )
        return result.scalar()


def _get_countries(driver: Driver) -> list[str]:
    """Neo4j Country 노드에서 국가 코드 목록을 가져온다."""
    with driver.session() as session:
        result = session.run("MATCH (c:Country) RETURN c.code AS code ORDER BY c.code")
        return [r["code"] for r in result]


def _get_product_types(driver: Driver) -> list[dict]:
    """Neo4j ProductType 노드에서 유형 목록을 가져온다.

    Returns:
        [{"en": "sunscreen", "ko": "선크림"}, ...]
    """
    with driver.session() as session:
        result = session.run(
            "MATCH (t:ProductType) RETURN t.nameEn AS en, t.name AS ko ORDER BY t.nameEn"
        )
        return [{"en": r["en"], "ko": r["ko"]} for r in result]


# ── 축 1: 패턴 탐지 현황 ──────────────────────────────────────────


def eval_pattern_discovery(engine: Engine, driver: Driver) -> dict:
    """PatternScout의 패턴 탐지 현황.

    relationship_proposals 테이블이 없으면 전부 0.
    Step 5에서 테이블을 만들면 자동으로 수치가 채워짐.
    """
    if not _table_exists(engine, "relationship_proposals"):
        proposals = {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
        by_type = {}
    else:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT count(*) AS total,
                           count(*) FILTER (WHERE status = 'approved') AS approved,
                           count(*) FILTER (WHERE status = 'rejected') AS rejected,
                           count(*) FILTER (WHERE status = 'proposed') AS pending
                    FROM relationship_proposals
                """)
            ).mappings().one()
            proposals = dict(row)

            types = conn.execute(
                text("""
                    SELECT relationship_type, count(*) AS cnt
                    FROM relationship_proposals WHERE status != 'rejected'
                    GROUP BY 1
                """)
            ).mappings().all()
            by_type = {t["relationship_type"]: t["cnt"] for t in types}

    with driver.session() as session:
        seed_result = session.run(
            "MATCH ()-[r]->() "
            "WHERE NOT type(r) IN ['PROPOSED_LINK', 'DISCOVERED_LINK'] "
            "RETURN count(r) AS c"
        )
        seed_rels = seed_result.single()["c"]

        disc_result = session.run(
            "MATCH ()-[r:DISCOVERED_LINK]->() RETURN count(r) AS c"
        )
        discovered = disc_result.single()["c"]

    total_rels = seed_rels + discovered
    return {
        "total_proposed": proposals["total"],
        "approved": proposals["approved"],
        "rejected": proposals["rejected"],
        "pending": proposals["pending"],
        "approval_rate": round(proposals["approved"] / max(proposals["total"], 1), 2),
        "seed_relations": seed_rels,
        "discovered_relations": discovered,
        "relation_growth": round(total_rels / max(seed_rels, 1), 2),
        "by_type": by_type,
    }


# ── 축 2: 답변 품질 개선률 ──────────────────────────────────────────


def _has_discovered_links(steps: list[dict]) -> bool:
    """steps에서 query_causal_chain의 tool_output에 비어있지 않은 discovered_links가 있는지."""
    for step in steps:
        if step.get("type") != "tool_call":
            continue
        if step.get("tool") != "query_causal_chain":
            continue
        output = step.get("tool_output")
        if not isinstance(output, (dict, list)):
            continue
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict) and item.get("discovered_links"):
                    return True
        if isinstance(output, dict) and output.get("discovered_links"):
            return True
    return False


def eval_answer_quality(engine: Engine) -> dict:
    """승인된 관계(DISCOVERED_LINK)가 실제 답변에 사용되고 있는가.

    orchestrator_results.steps JSONB에서 판별.
    tool_call_traces는 10KB 잘림이 있으므로 사용하지 않음.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT trace_id, steps FROM orchestrator_results ORDER BY created_at")
        ).mappings().all()

    total = len(rows)
    used_discovered = 0
    session_history = []

    for row in rows:
        steps = row["steps"] if isinstance(row["steps"], list) else json.loads(row["steps"])
        has_disc = _has_discovered_links(steps)
        if has_disc:
            used_discovered += 1
        session_history.append({
            "trace_id": row["trace_id"],
            "used_discovered": has_disc,
        })

    return {
        "total_analyses": total,
        "used_discovered_link": used_discovered,
        "discovered_usage_rate": round(used_discovered / max(total, 1), 2),
        "session_history": session_history,
    }


# ── 축 3: 추론 커버리지 ──────────────────────────────────────────


MIN_DATA_THRESHOLD = 30  # 통계적으로 의미 있는 최소 건수
MIN_ATTR_DIVERSITY = 2   # 트렌드 비교가 가능한 최소 속성 종류


def eval_reasoning_coverage(engine: Engine, driver: Driver) -> dict:
    """데이터 근거로 답할 수 있는 범위 — 국가×유형 매트릭스.

    셀(국가×유형) 단위로 3가지를 평가:
      1. causal: 이 국가+유형에 맞는 인과 체인이 Neo4j에 존재하는가
      2. data: 주문+추출 데이터가 통계적으로 유의미한 양(30건+) 존재하는가
      3. diversity: 추출된 속성이 2종 이상이어서 트렌드 비교가 가능한가

    full = causal + data + diversity 모두 충족
    각 셀에 부족한 것과 필요한 액션을 함께 반환.
    """
    countries = _get_countries(driver)
    product_types = _get_product_types(driver)
    total_cells = len(countries) * len(product_types)

    # orchestrator_results에서 causal_chain 호출 비율
    with engine.connect() as conn:
        total_result = conn.execute(
            text("SELECT count(*) AS c FROM orchestrator_results")
        ).mappings().one()
        total_analyses = total_result["c"]

        with_causal_result = conn.execute(
            text("""
                SELECT count(*) AS c FROM orchestrator_results
                WHERE steps::text LIKE '%query_causal_chain%'
            """)
        ).mappings().one()
        with_causal = with_causal_result["c"]

    # 국가별 인과 체인이 커버하는 Function 목록 미리 조회
    country_functions: dict[str, set[str]] = {}
    with driver.session() as session:
        func_result = session.run("""
            MATCH (co:Country)-[:HAS_CLIMATE]->()-[:TRIGGERS]->()
                  -[:DRIVES_DEMAND]->(f:Function)
            RETURN co.code AS country, collect(DISTINCT f.name) AS functions
        """)
        for r in func_result:
            country_functions[r["country"]] = set(r["functions"])

    # 유형별 주요 Function 매핑 (이 유형에서 의미 있는 기능)
    type_relevant_functions: dict[str, set[str]] = {}
    with driver.session() as session:
        tf_result = session.run("""
            MATCH (p:Product)-[:IS_TYPE]->(t:ProductType),
                  (p)-[:CONTAINS]->(:Ingredient)-[:HAS_FUNCTION]->(f:Function)
            RETURN t.nameEn AS type, collect(DISTINCT f.name) AS functions
        """)
        for r in tf_result:
            type_relevant_functions[r["type"]] = set(r["functions"])

    # 국가×유형 매트릭스
    coverage = {}
    for country in countries:
        for pt in product_types:
            # causal: 이 국가의 인과 체인이 이 유형에 관련된 Function을 커버하는가
            c_funcs = country_functions.get(country, set())
            t_funcs = type_relevant_functions.get(pt["en"], set())
            has_causal = bool(c_funcs & t_funcs)  # 교집합 존재 여부

            # DISCOVERED_LINK도 체크 (PatternScout 발견)
            with driver.session() as session:
                disc_result = session.run(
                    "MATCH ()-[r:DISCOVERED_LINK]->() RETURN count(r) > 0 AS exists"
                )
                has_discovered = disc_result.single()["exists"]

            # data: 충분한 양의 주문 데이터 존재 여부
            with engine.connect() as conn:
                data_result = conn.execute(
                    text("""
                        SELECT count(*) AS cnt
                        FROM orders_unified o
                        JOIN extractions e ON e.order_id = o.order_id
                        WHERE o.destination_country = :c
                          AND e.attributes->>'productType' = :pt
                    """),
                    {"c": country, "pt": pt["ko"]},
                ).mappings().one()
                data_count = data_result["cnt"]
                has_data = data_count >= MIN_DATA_THRESHOLD

                # diversity: 속성 종류 수
                div_result = conn.execute(
                    text("""
                        SELECT count(DISTINCT attr) AS cnt
                        FROM (
                            SELECT jsonb_array_elements_text(e.attributes->'functionalClaims') AS attr
                            FROM extractions e
                            JOIN orders_unified o ON e.order_id = o.order_id
                            WHERE o.destination_country = :c
                              AND e.attributes->>'productType' = :pt
                            UNION ALL
                            SELECT jsonb_array_elements_text(e.attributes->'valueClaims') AS attr
                            FROM extractions e
                            JOIN orders_unified o ON e.order_id = o.order_id
                            WHERE o.destination_country = :c
                              AND e.attributes->>'productType' = :pt
                        ) sub
                    """),
                    {"c": country, "pt": pt["ko"]},
                ).mappings().one()
                attr_diversity = div_result["cnt"]
                has_diversity = attr_diversity >= MIN_ATTR_DIVERSITY

            causal_ok = has_causal or has_discovered
            is_full = causal_ok and has_data and has_diversity

            # 부족한 것 + 액션 가이드
            gaps = []
            if not causal_ok:
                gaps.append("인과 체인 없음 → 이 국가+유형의 기후/피부고민/기능 관계를 시드하세요")
            if not has_data:
                gaps.append(f"데이터 부족({data_count}건) → {MIN_DATA_THRESHOLD}건 이상 주문 데이터 필요")
            if not has_diversity:
                gaps.append(f"속성 단조({attr_diversity}종) → {MIN_ATTR_DIVERSITY}종 이상 속성이 있어야 비교 가능")

            cell_key = f"{country}_{pt['en']}"
            coverage[cell_key] = {
                "causal": causal_ok,
                "data": has_data,
                "diversity": has_diversity,
                "full": is_full,
                "data_count": data_count,
                "attr_diversity": attr_diversity,
                "gaps": gaps,
            }

    full_count = sum(1 for v in coverage.values() if v["full"])

    return {
        "causal_evidence_rate": round(with_causal / max(total_analyses, 1), 2),
        "full_coverage_cells": full_count,
        "total_cells": total_cells,
        "full_coverage_rate": round(full_count / max(total_cells, 1), 2),
        "matrix": coverage,
    }


# ── 축 4: 시스템 효율 ──────────────────────────────────────────


def eval_system_efficiency(engine: Engine) -> dict:
    """비용-품질 트레이드오프 추적.

    세션별로 agent_type(analyst/pattern_scout)별 비용을 분리 집계하고,
    DISCOVERED_LINK 활용 여부와 연결하여
    "답변 품질 개선에 추가 비용이 얼마나 드는가"를 정량화한다.
    """
    # 1. 세션별 agent_type별 비용 분리
    with engine.connect() as conn:
        cost_rows = conn.execute(
            text("""
                SELECT
                    t.trace_id,
                    COALESCE(SUM(t.cost_usd) FILTER (WHERE t.agent_type = 'analyst'), 0) AS analyst_cost,
                    COALESCE(SUM(t.cost_usd) FILTER (WHERE t.agent_type = 'pattern_scout'), 0) AS scout_cost,
                    COALESCE(SUM(t.cost_usd), 0) AS total_cost
                FROM tool_call_traces t
                WHERE t.trace_id IN (SELECT trace_id FROM orchestrator_results)
                GROUP BY t.trace_id
            """)
        ).mappings().all()
        cost_map = {r["trace_id"]: dict(r) for r in cost_rows}

        # 2. orchestrator_results에서 질문 + steps (discovered 판별용)
        result_rows = conn.execute(
            text("""
                SELECT trace_id, user_query, steps, total_cost_usd, created_at
                FROM orchestrator_results
                ORDER BY created_at
            """)
        ).mappings().all()

    sessions = []
    for r in result_rows:
        tid = r["trace_id"]
        costs = cost_map.get(tid, {})
        steps = r["steps"] if isinstance(r["steps"], list) else json.loads(r["steps"])
        used_disc = _has_discovered_links(steps)

        sessions.append({
            "trace_id": tid,
            "user_query": r["user_query"],
            "created_at": str(r["created_at"]),
            "analyst_cost": round(float(costs.get("analyst_cost", 0)), 6),
            "scout_cost": round(float(costs.get("scout_cost", 0)), 6),
            "total_cost": round(float(costs.get("total_cost", 0) or r["total_cost_usd"]), 6),
            "used_discovered": used_disc,
        })

    if len(sessions) < 1:
        return {"status": "insufficient_data", "sessions": []}

    # 3. 요약 통계
    total_sessions = len(sessions)
    avg_analyst = sum(s["analyst_cost"] for s in sessions) / total_sessions
    avg_scout = sum(s["scout_cost"] for s in sessions) / total_sessions
    avg_total = sum(s["total_cost"] for s in sessions) / total_sessions

    with_disc = [s for s in sessions if s["used_discovered"]]
    without_disc = [s for s in sessions if not s["used_discovered"]]

    avg_with = sum(s["total_cost"] for s in with_disc) / len(with_disc) if with_disc else 0
    avg_without = sum(s["total_cost"] for s in without_disc) / len(without_disc) if without_disc else 0

    return {
        "status": "ok",
        "sessions": sessions,
        "summary": {
            "total_sessions": total_sessions,
            "avg_analyst_cost": round(avg_analyst, 6),
            "avg_scout_cost": round(avg_scout, 6),
            "avg_total_cost": round(avg_total, 6),
            "scout_cost_ratio": round(avg_scout / max(avg_total, 0.000001), 2),
            "with_discovered": {
                "count": len(with_disc),
                "avg_total_cost": round(avg_with, 6),
            },
            "without_discovered": {
                "count": len(without_disc),
                "avg_total_cost": round(avg_without, 6),
            },
            "quality_premium": round(avg_with - avg_without, 6) if with_disc and without_disc else None,
        },
    }


# ── Before/After 답변 비교 ──────────────────────────────────────


def find_before_after_pairs(engine: Engine) -> list[dict]:
    """같은 질문이 승인 전/후로 실행된 쌍을 찾는다.

    orchestrator_results에서 같은 user_query가 2회 이상 실행된 것을 찾고,
    discovered_links 유무로 before(없음)/after(있음)를 구분.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT trace_id, user_query, answer, steps, created_at
                FROM orchestrator_results
                WHERE user_query IN (
                    SELECT user_query FROM orchestrator_results
                    GROUP BY user_query HAVING count(*) >= 2
                )
                ORDER BY user_query, created_at
            """)
        ).mappings().all()

    by_query: dict[str, list[dict]] = {}
    for row in rows:
        q = row["user_query"]
        if q not in by_query:
            by_query[q] = []
        steps = row["steps"] if isinstance(row["steps"], list) else json.loads(row["steps"])
        by_query[q].append({
            "trace_id": row["trace_id"],
            "answer": row["answer"],
            "has_discovered": _has_discovered_links(steps),
            "created_at": str(row["created_at"]),
        })

    pairs = []
    for query, runs in by_query.items():
        before_runs = [r for r in runs if not r["has_discovered"]]
        after_runs = [r for r in runs if r["has_discovered"]]

        if before_runs and after_runs:
            before = before_runs[-1]
            after = after_runs[-1]
            pairs.append({
                "query": query,
                "before_trace_id": before["trace_id"],
                "before_answer": before["answer"],
                "before_at": before["created_at"],
                "after_trace_id": after["trace_id"],
                "after_answer": after["answer"],
                "after_at": after["created_at"],
            })

    return pairs


# ── 통합 Eval ──────────────────────────────────────────


def run_full_eval(engine: Engine, driver: Driver) -> dict:
    """4축 통합 + before_after_pairs."""
    return {
        "pattern_discovery": eval_pattern_discovery(engine, driver),
        "answer_quality": eval_answer_quality(engine),
        "reasoning_coverage": eval_reasoning_coverage(engine, driver),
        "system_efficiency": eval_system_efficiency(engine),
        "before_after_pairs": find_before_after_pairs(engine),
    }
