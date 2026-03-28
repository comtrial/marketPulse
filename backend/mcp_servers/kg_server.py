"""Neo4j 지식 그래프 도구 서버.

온톨로지 기반 인과 체인, 성분 트렌딩, 상품 그래프, 성분 시너지를 제공한다.

도구 스키마 관리:
  각 도구의 입력을 Pydantic BaseModel로 정의하고 @tool 데코레이터를 부착.
  → Anthropic Tool의 input_schema가 Pydantic model_json_schema()에서 자동 생성
  → 함수의 docstring이 Tool description이 됨
  → 스키마를 수동으로 쓰지 않으므로 함수 시그니처와 항상 동기화

Neo4j가 답하는 것: "왜?" — 인과 체인, 관계 탐색
PostgreSQL이 답하는 것: "얼마나?" — 집계, 시계열 (order_server.py)
"""

from typing import Literal

import structlog
from neo4j import Driver
from pydantic import BaseModel, Field

from orchestrator.tool_decorator import tool

logger = structlog.get_logger()


# ── 입력 스키마 (Pydantic) ──────────────────────────────────────


class QueryCausalChainInput(BaseModel):
    country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")


class FindTrendingIngredientsInput(BaseModel):
    country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")
    product_type: Literal["sunscreen", "toner", "serum", "cream", "lip"] | None = Field(
        default=None, description="제품 유형 필터. None이면 전체"
    )
    top_k: int = Field(default=5, description="상위 N개")


class GetProductGraphInput(BaseModel):
    product_id: str = Field(description="Product 노드의 id (order_id)")


class FindIngredientSynergiesInput(BaseModel):
    ingredient_ko: str = Field(description="성분 한국어명 (예: 히알루론산)")


# ── 서버 클래스 ──────────────────────────────────────────────────


class KnowledgeGraphServer:
    """Neo4j 지식 그래프 도구 4개를 제공하는 서버.

    도구 목록:
      1. query_causal_chain — 기후→피부고민→기능 인과 체인
      2. find_trending_ingredients — 성분별 상품 등장 빈도
      3. get_product_graph — 상품의 전체 그래프 컨텍스트
      4. find_ingredient_synergies — 명시적 시너지 + co-occurrence
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    @tool(QueryCausalChainInput)
    def query_causal_chain(self, params: QueryCausalChainInput) -> list[dict]:
        """특정 국가의 기후→피부고민→기능 수요 인과 체인을 반환. '이 나라에서 뭐가 왜 잘 팔리는지' 질문에 사용."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Country {code: $code})-[:HAS_CLIMATE]->(cz:ClimateZone)
                      -[t:TRIGGERS]->(sc:SkinConcern)
                      -[d:DRIVES_DEMAND]->(f:Function)
                WHERE t.strength > 0.5 AND d.strength > 0.5
                RETURN cz.type AS climate,
                       sc.nameKo AS skinConcern,
                       t.strength AS triggerStrength,
                       t.season AS season,
                       t.mechanism AS mechanism,
                       f.name AS function,
                       d.strength AS demandStrength,
                       round(t.strength * d.strength * 100) / 100.0 AS chainStrength
                ORDER BY chainStrength DESC
                """,
                code=params.country_code,
            )
            chains = [record.data() for record in result]

        logger.info("causal_chain_queried", country=params.country_code, chains_found=len(chains))
        return chains

    @tool(FindTrendingIngredientsInput)
    def find_trending_ingredients(self, params: FindTrendingIngredientsInput) -> list[dict]:
        """특정 국가에서 성분별 상품 등장 빈도를 반환. '어떤 성분이 많이 쓰이는가' 질문에 사용."""
        with self.driver.session() as session:
            neo4j_params: dict = {"code": params.country_code, "topk": params.top_k}

            if params.product_type:
                cypher = """
                    MATCH (p:Product)-[:SOLD_IN]->(c:Country {code: $code})
                    MATCH (p)-[:IS_TYPE]->(t:ProductType {nameEn: $ptype})
                    MATCH (p)-[:CONTAINS]->(i:Ingredient)
                    RETURN i.commonNameKo AS ingredient,
                           i.inciName AS inci,
                           count(DISTINCT p) AS productCount,
                           collect(DISTINCT p.name)[..3] AS exampleProducts
                    ORDER BY productCount DESC
                    LIMIT $topk
                """
                neo4j_params["ptype"] = params.product_type
            else:
                cypher = """
                    MATCH (p:Product)-[:SOLD_IN]->(c:Country {code: $code})
                    MATCH (p)-[:CONTAINS]->(i:Ingredient)
                    RETURN i.commonNameKo AS ingredient,
                           i.inciName AS inci,
                           count(DISTINCT p) AS productCount,
                           collect(DISTINCT p.name)[..3] AS exampleProducts
                    ORDER BY productCount DESC
                    LIMIT $topk
                """

            result = session.run(cypher, **neo4j_params)
            ingredients = [record.data() for record in result]

        logger.info(
            "trending_ingredients_queried",
            country=params.country_code,
            product_type=params.product_type,
            results=len(ingredients),
        )
        return ingredients

    @tool(GetProductGraphInput)
    def get_product_graph(self, params: GetProductGraphInput) -> dict:
        """특정 상품의 성분, 기능, 판매국가, 플랫폼 등 전체 그래프 컨텍스트를 반환."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Product {id: $pid})
                OPTIONAL MATCH (p)-[:CONTAINS]->(i:Ingredient)
                               -[:HAS_FUNCTION]->(f:Function)
                OPTIONAL MATCH (p)-[:SOLD_IN]->(c:Country)
                OPTIONAL MATCH (p)-[:SOLD_ON]->(pl:Platform)
                OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
                OPTIONAL MATCH (p)-[:IS_TYPE]->(t:ProductType)
                RETURN p.name AS name,
                       p.functionalClaims AS functionalClaims,
                       p.valueClaims AS valueClaims,
                       collect(DISTINCT {
                           ingredient: i.commonNameKo,
                           inci: i.inciName,
                           function: f.name
                       }) AS ingredients,
                       collect(DISTINCT c.code) AS countries,
                       collect(DISTINCT pl.name) AS platforms,
                       b.name AS brand,
                       t.nameEn AS productType
                """,
                pid=params.product_id,
            )
            record = result.single()
            return record.data() if record else {}

    @tool(FindIngredientSynergiesInput)
    def find_ingredient_synergies(self, params: FindIngredientSynergiesInput) -> list[dict]:
        """특정 성분과 시너지를 내는 성분을 찾음. 명시적 시너지 관계 + 동일 상품 co-occurrence 기반."""
        with self.driver.session() as session:
            explicit_result = session.run(
                """
                MATCH (i:Ingredient {commonNameKo: $ingr})
                      -[s:SYNERGIZES_WITH]-(other:Ingredient)
                RETURN other.commonNameKo AS partner,
                       s.mechanism AS mechanism,
                       'explicit_synergy' AS source
                """,
                ingr=params.ingredient_ko,
            )
            explicit = [r.data() for r in explicit_result]

            co_result = session.run(
                """
                MATCH (i:Ingredient {commonNameKo: $ingr})
                      <-[:CONTAINS]-(p:Product)-[:CONTAINS]->(other:Ingredient)
                WHERE other.commonNameKo <> $ingr
                RETURN other.commonNameKo AS partner,
                       count(p) AS coCount,
                       'co_occurrence' AS source
                ORDER BY coCount DESC
                LIMIT 5
                """,
                ingr=params.ingredient_ko,
            )
            co_occurrence = []
            for r in co_result:
                data = r.data()
                data["mechanism"] = f"{data.pop('coCount')}개 상품에서 함께 등장"
                co_occurrence.append(data)

        synergies = explicit + co_occurrence
        logger.info(
            "ingredient_synergies_queried",
            ingredient=params.ingredient_ko,
            explicit=len(explicit),
            co_occurrence=len(co_occurrence),
        )
        return synergies
