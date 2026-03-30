"""Logic 도구 서버 — 통계 검증을 코드로 수행.

LLM은 "어떤 속성 쌍을 검사할지"만 판단하고,
lift·correlation·p-value 계산은 이 서버의 SQL + scipy가 수행한다.
LLM이 생성한 숫자는 재현·검증 불가하므로 사용하지 않는다 (ADR-017).

도구 3개:
  compute_cooccurrence_lift — 두 속성의 동시 출현 lift
  compute_temporal_correlation — 두 속성의 시계열 상관계수
  test_hypothesis — 범용 가설 검증 (국가 간 비율 비교 등)

상수 하드코딩 없음 — 제품 유형 매핑은 Neo4j에서 동적 조회 (ADR-015).
"""

import json

import structlog
from neo4j import Driver
from pydantic import BaseModel, Field
from scipy import stats
from sqlalchemy import text
from sqlalchemy.engine import Engine

from orchestrator.tool_decorator import tool

logger = structlog.get_logger()


def _build_product_type_map(driver: Driver) -> dict[str, str]:
    """Neo4j ProductType 노드에서 nameEn→name(한글) 매핑을 동적으로 구축."""
    with driver.session() as session:
        result = session.run("MATCH (t:ProductType) RETURN t.nameEn AS en, t.name AS ko")
        return {r["en"]: r["ko"] for r in result}


# ── 입력 스키마 ──


class CooccurrenceLiftInput(BaseModel):
    attr_a: str = Field(description="속성 A (예: 비건)")
    attr_b: str = Field(description="속성 B (예: 무기자차)")
    country: str = Field(description="국가 코드 (KR/JP/SG)")
    product_type: str = Field(description="제품 유형 (sunscreen/toner/...)")


class TemporalCorrelationInput(BaseModel):
    attr_a: str = Field(description="속성 A")
    attr_b: str = Field(description="속성 B")
    country: str = Field(description="국가 코드")
    max_lag_months: int = Field(default=3, description="최대 시차 (개월)")


class TestHypothesisInput(BaseModel):
    hypothesis_type: str = Field(description="가설 유형: attribute_comparison")
    params: dict = Field(description="가설 파라미터")


# ── 속성 검색 SQL 헬퍼 ──


def _attr_filter_sql(param_prefix: str) -> str:
    """속성이 valueClaims, functionalClaims, additionalAttrs 중 어디에 있든 검색하는 SQL.

    ADR-011(원본 키워드 보존)에 따라 3곳 모두 검색.
    무기자차는 additionalAttrs에, 비건은 valueClaims에, 톤업은 functionalClaims에 있으므로.
    """
    return f"""(
        e.attributes->'valueClaims' @> CAST(:{param_prefix}_json AS jsonb)
        OR e.attributes->'functionalClaims' @> CAST(:{param_prefix}_json AS jsonb)
        OR EXISTS (
            SELECT 1 FROM jsonb_each_text(e.attributes->'additionalAttrs') AS x(k,v)
            WHERE x.v = :{param_prefix}_raw
        )
    )"""


# ── 서버 ──


class LogicServer:
    """통계 검증 도구 3개. 코드가 계산, LLM은 파라미터만 선택."""

    def __init__(self, engine: Engine, neo4j_driver: Driver):
        self.engine = engine
        self._type_map = _build_product_type_map(neo4j_driver)

    def _resolve_ptype(self, ptype: str) -> str:
        """영문 유형 → 한글. Neo4j에서 동적 조회한 매핑 사용."""
        return self._type_map.get(ptype, ptype)

    @tool(CooccurrenceLiftInput)
    def compute_cooccurrence_lift(self, params: CooccurrenceLiftInput) -> dict:
        """두 속성의 동시 출현 lift를 계산. lift > 1.3이면 SYNERGY 제안 후보."""
        ptype_ko = self._resolve_ptype(params.product_type)
        fa = _attr_filter_sql("a")
        fb = _attr_filter_sql("b")

        with self.engine.connect() as conn:
            result = conn.execute(
                text(f"""
                    WITH base AS (
                        SELECT e.attributes
                        FROM extractions e
                        JOIN orders_unified o ON e.order_id = o.order_id
                        WHERE o.destination_country = :country
                          AND e.attributes->>'productType' = :ptype
                    ),
                    counts AS (
                        SELECT
                            COUNT(*) AS total,
                            COUNT(*) FILTER (WHERE {fa}) AS has_a,
                            COUNT(*) FILTER (WHERE {fb}) AS has_b,
                            COUNT(*) FILTER (WHERE {fa} AND {fb}) AS has_both
                        FROM base e
                    )
                    SELECT total, has_a, has_b, has_both FROM counts
                """),
                {
                    "country": params.country,
                    "ptype": ptype_ko,
                    "a_json": json.dumps([params.attr_a]),
                    "a_raw": params.attr_a,
                    "b_json": json.dumps([params.attr_b]),
                    "b_raw": params.attr_b,
                },
            ).mappings().one()

        total = result["total"]
        has_a, has_b, has_both = result["has_a"], result["has_b"], result["has_both"]

        rate_a = has_a / total if total > 0 else 0
        rate_b = has_b / total if total > 0 else 0
        rate_both = has_both / total if total > 0 else 0
        expected = rate_a * rate_b
        lift = rate_both / expected if expected > 0 else 0

        logger.info("cooccurrence_lift_computed", a=params.attr_a, b=params.attr_b, lift=round(lift, 2), n=total)
        return {
            "attr_a": params.attr_a,
            "attr_b": params.attr_b,
            "country": params.country,
            "product_type": params.product_type,
            "rate_a": round(rate_a, 3),
            "rate_b": round(rate_b, 3),
            "rate_both": round(rate_both, 3),
            "expected": round(expected, 3),
            "lift": round(lift, 2),
            "evidence_strength": "strong" if lift > 2.0 else "moderate" if lift > 1.3 else "weak",
            "sample_size": total,
        }

    @tool(TemporalCorrelationInput)
    def compute_temporal_correlation(self, params: TemporalCorrelationInput) -> dict:
        """두 속성의 시계열 상관계수를 계산. |r| > 0.6이면 TEMPORAL_CORRELATION 제안 후보."""
        fa = _attr_filter_sql("a")
        fb = _attr_filter_sql("b")

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                    SELECT
                        CAST(DATE_TRUNC('month', o.order_date) AS date) AS month,
                        COUNT(*) AS total,
                        CAST(COUNT(*) FILTER (WHERE {fa}) AS float)
                            / NULLIF(COUNT(*), 0) AS rate_a,
                        CAST(COUNT(*) FILTER (WHERE {fb}) AS float)
                            / NULLIF(COUNT(*), 0) AS rate_b
                    FROM orders_unified o
                    JOIN extractions e ON e.order_id = o.order_id
                    WHERE o.destination_country = :country
                    GROUP BY 1 ORDER BY 1
                """),
                {
                    "country": params.country,
                    "a_json": json.dumps([params.attr_a]),
                    "a_raw": params.attr_a,
                    "b_json": json.dumps([params.attr_b]),
                    "b_raw": params.attr_b,
                },
            ).mappings().all()

        series_a = [float(r["rate_a"] or 0) for r in rows]
        series_b = [float(r["rate_b"] or 0) for r in rows]

        if len(series_a) < 3:
            return {"attr_a": params.attr_a, "attr_b": params.attr_b, "status": "insufficient_data", "data_points": len(series_a)}

        best_lag, best_corr = 0, 0.0
        for lag in range(-params.max_lag_months, params.max_lag_months + 1):
            if lag >= 0:
                a, b = series_a[lag:], series_b[:len(series_a) - lag]
            else:
                b, a = series_b[-lag:], series_a[:len(series_b) + lag]
            if len(a) < 3:
                continue
            corr, _ = stats.pearsonr(a, b)
            if abs(corr) > abs(best_corr):
                best_corr, best_lag = corr, lag

        logger.info("temporal_correlation_computed", a=params.attr_a, b=params.attr_b, corr=round(best_corr, 3))
        return {
            "attr_a": params.attr_a,
            "attr_b": params.attr_b,
            "country": params.country,
            "best_lag_months": best_lag,
            "correlation": round(best_corr, 3),
            "direction": "positive" if best_corr > 0 else "negative",
            "evidence_strength": "strong" if abs(best_corr) > 0.7 else "moderate" if abs(best_corr) > 0.4 else "weak",
            "data_points": len(series_a),
        }

    @tool(TestHypothesisInput)
    def test_hypothesis(self, params: TestHypothesisInput) -> dict:
        """범용 가설 검증. 구조화된 절차 외 추가 패턴 탐색용."""
        handlers = {"attribute_comparison": self._test_comparison}
        handler = handlers.get(params.hypothesis_type)
        if not handler:
            return {"status": "unsupported", "supported_types": list(handlers.keys())}
        return handler(params.params)

    def _test_comparison(self, p: dict) -> dict:
        """두 국가의 같은 속성 비율을 비교 (Fisher exact test)."""
        group_a = p.get("group_a", {})
        group_b = p.get("group_b", {})
        attr = group_a.get("attr", group_b.get("attr", ""))
        fx = _attr_filter_sql("x")

        results = {}
        for label, g in [("a", group_a), ("b", group_b)]:
            ptype_ko = self._resolve_ptype(g.get("type", ""))
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(f"""
                        SELECT COUNT(*) AS total,
                               COUNT(*) FILTER (WHERE {fx}) AS hit
                        FROM orders_unified o
                        JOIN extractions e ON e.order_id = o.order_id
                        WHERE o.destination_country = :c
                          AND e.attributes->>'productType' = :pt
                    """),
                    {"c": g.get("country", ""), "pt": ptype_ko, "x_json": json.dumps([attr]), "x_raw": attr},
                ).mappings().one()
            results[label] = {"total": row["total"], "hit": row["hit"]}

        a_t, a_h = results["a"]["total"], results["a"]["hit"]
        b_t, b_h = results["b"]["total"], results["b"]["hit"]
        _, p_value = stats.fisher_exact([[a_h, a_t - a_h], [b_h, b_t - b_h]])

        return {
            "hypothesis_type": "attribute_comparison",
            "attribute": attr,
            "group_a": {**group_a, "rate": round(a_h / a_t, 3) if a_t else 0, "count": a_h, "total": a_t},
            "group_b": {**group_b, "rate": round(b_h / b_t, 3) if b_t else 0, "count": b_h, "total": b_t},
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
        }
