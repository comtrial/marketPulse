"""주문 데이터 도구 서버.

PostgreSQL의 orders_unified + extractions를 기반으로
속성 트렌드, 국가별 히트맵, 블루오션 분석을 제공한다.

도구 스키마 관리:
  @tool 데코레이터 + Pydantic BaseModel로 Anthropic Tool 스키마 자동 생성.
  kg_server.py와 동일 패턴.

PostgreSQL이 답하는 것: "얼마나?" — 집계, 시계열, 비율
Neo4j가 답하는 것: "왜?" — 인과 체인, 관계 탐색 (kg_server.py)
"""

import json
from typing import Literal

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine

from orchestrator.tool_decorator import tool

logger = structlog.get_logger()


# ── 입력 스키마 (Pydantic) ──────────────────────────────────────


class GetAttributeTrendInput(BaseModel):
    attribute_name: str = Field(description="속성명 (예: 비건, 톤업, 워터프루프)")
    attribute_type: Literal["functional", "value", "ingredient"] = Field(
        description="속성 분류"
    )
    countries: list[str] = Field(description="국가 코드 배열 (예: ['JP', 'SG'])")
    months: int = Field(default=6, description="조회 기간 (개월)")


class GetHeatmapInput(BaseModel):
    product_type: Literal["sunscreen", "toner", "serum", "cream", "lip"] = Field(
        description="제품 유형"
    )
    period_start: str = Field(description="시작월 (YYYY-MM)")
    period_end: str = Field(description="종료월 (YYYY-MM)")


class GetBlueOceanInput(BaseModel):
    product_type: str = Field(description="제품 유형")
    country: str = Field(description="국가 코드")
    top_k: int = Field(default=10, description="상위 N개")


class CompareSellerInput(BaseModel):
    seller_product_attrs: dict = Field(description="셀러 상품 속성 dict")
    country: str = Field(description="국가 코드")
    product_type: str = Field(description="제품 유형")


# ── 서버 클래스 ──────────────────────────────────────────────────


class OrderDataServer:
    """주문 데이터 도구 4개를 제공하는 서버.

    도구 목록:
      1. get_attribute_trend — 속성별 월별 비율 시계열 (핵심)
      2. get_country_attribute_heatmap — 국가×속성 비율 매트릭스
      3. get_blue_ocean_combinations — Phase 2 스텁
      4. compare_seller_vs_market — Phase 2 스텁
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    @tool(GetAttributeTrendInput)
    def get_attribute_trend(self, params: GetAttributeTrendInput) -> dict:
        """특정 속성의 국가별 월별 비율 추이를 반환. '비건이 일본에서 몇 %인지 6개월 추이' 같은 질문에 사용."""
        field_map = {
            "functional": "functionalClaims",
            "value": "valueClaims",
            "ingredient": "keyIngredients",
        }
        json_field = field_map.get(params.attribute_type, "valueClaims")
        attr_json = json.dumps([params.attribute_name])

        with self.engine.connect() as conn:
            result = conn.execute(
                text(f"""
                    WITH monthly AS (
                        SELECT
                            o.destination_country AS country,
                            DATE_TRUNC('month', o.order_date)::date AS month,
                            COUNT(*) AS total,
                            COUNT(*) FILTER (
                                WHERE e.attributes->'{json_field}' @> :attr_json::jsonb
                            ) AS with_attr
                        FROM orders_unified o
                        JOIN extractions e ON o.order_id = e.order_id
                        WHERE o.destination_country = ANY(:countries)
                        GROUP BY o.destination_country, DATE_TRUNC('month', o.order_date)
                    )
                    SELECT country, month, total, with_attr,
                           ROUND(with_attr::numeric / NULLIF(total, 0) * 100, 1) AS percentage
                    FROM monthly
                    ORDER BY country, month
                """),
                {"attr_json": attr_json, "countries": params.countries},
            )

            by_country: dict[str, list[dict]] = {}
            for row in result.mappings():
                c = row["country"]
                if c not in by_country:
                    by_country[c] = []
                by_country[c].append({
                    "month": row["month"].strftime("%Y-%m"),
                    "total": row["total"],
                    "withAttr": row["with_attr"],
                    "percentage": float(row["percentage"] or 0),
                })

        logger.info("attribute_trend_queried", attribute=params.attribute_name, countries=params.countries)
        return {"attribute": params.attribute_name, "type": params.attribute_type, "trend": by_country}

    @tool(GetHeatmapInput)
    def get_country_attribute_heatmap(self, params: GetHeatmapInput) -> dict:
        """국가별 × 속성별 비율 매트릭스를 반환. 히트맵 시각화의 데이터 소스."""
        type_map = {
            "sunscreen": "선크림", "toner": "토너", "serum": "세럼",
            "cream": "크림", "lip": "립",
        }
        product_type_ko = type_map.get(params.product_type, params.product_type)

        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    WITH base AS (
                        SELECT o.destination_country AS country, e.attributes
                        FROM orders_unified o
                        JOIN extractions e ON o.order_id = e.order_id
                        WHERE e.attributes->>'productType' = :ptype
                          AND o.order_date >= :start_date::date
                          AND o.order_date < (:end_date::date + INTERVAL '1 month')
                    ),
                    country_totals AS (
                        SELECT country, COUNT(*) AS total FROM base GROUP BY country
                    ),
                    functional_counts AS (
                        SELECT b.country, claim AS attribute, COUNT(*) AS cnt
                        FROM base b, jsonb_array_elements_text(b.attributes->'functionalClaims') AS claim
                        GROUP BY b.country, claim
                    ),
                    value_counts AS (
                        SELECT b.country, claim AS attribute, COUNT(*) AS cnt
                        FROM base b, jsonb_array_elements_text(b.attributes->'valueClaims') AS claim
                        GROUP BY b.country, claim
                    ),
                    all_counts AS (
                        SELECT * FROM functional_counts UNION ALL SELECT * FROM value_counts
                    )
                    SELECT a.country, a.attribute,
                           SUM(a.cnt) AS cnt,
                           ROUND(SUM(a.cnt)::numeric / ct.total * 100, 1) AS percentage
                    FROM all_counts a
                    JOIN country_totals ct ON a.country = ct.country
                    GROUP BY a.country, a.attribute, ct.total
                    HAVING SUM(a.cnt) >= 2
                    ORDER BY a.country, percentage DESC
                """),
                {
                    "ptype": product_type_ko,
                    "start_date": f"{params.period_start}-01",
                    "end_date": f"{params.period_end}-01",
                },
            )

            matrix: dict[str, dict[str, float]] = {}
            for row in result.mappings():
                country = row["country"]
                if country not in matrix:
                    matrix[country] = {}
                matrix[country][row["attribute"]] = float(row["percentage"])

        logger.info("heatmap_queried", product_type=params.product_type)
        return {
            "productType": params.product_type,
            "period": f"{params.period_start}~{params.period_end}",
            "matrix": matrix,
            "countries": list(matrix.keys()),
        }

    @tool(GetBlueOceanInput)
    def get_blue_ocean_combinations(self, params: GetBlueOceanInput) -> dict:
        """[Phase 2] 속성 조합별 수요 vs 공급 비교. 블루오션 조합 탐색."""
        return {"status": "phase2", "message": "Phase 2에서 구현 예정"}

    @tool(CompareSellerInput)
    def compare_seller_vs_market(self, params: CompareSellerInput) -> dict:
        """[Phase 2] 셀러 상품 속성과 시장 인기 속성 비교. 갭 분석."""
        return {"status": "phase2", "message": "Phase 2에서 구현 예정"}
