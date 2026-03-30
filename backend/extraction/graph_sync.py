"""추출 결과를 Neo4j 지식 그래프에 동기화.

이게 없으면 Neo4j는 정적 화이트보드, 있으면 살아있는 지식 그래프.

동기화 대상:
  - Product 노드 (NEW) — 추출할 때마다 생성
  - 관계 (NEW) — 기존 온톨로지 노드에 연결
    - [:MADE_BY]→Brand          ← LLM 추출 결과 (attrs["brand"])
    - [:IS_TYPE]→ProductType    ← 주문 데이터 (order.product_type)
    - [:CONTAINS]→Ingredient    ← LLM 추출 결과 (attrs["keyIngredients"])
    - [:SOLD_IN]→Country        ← 주문 데이터 (order.destination_country)
    - [:SOLD_ON]→Platform       ← 주문 데이터 (order.platform)

현재 제약:
  - 시드된 Ingredient 노드에 매칭되는 경우만 CONTAINS 관계 생성
  - 미매칭 성분은 로그만 남기고 skip
  - 잘못된 온톨로지 > 불완전한 온톨로지

SOLD_IN 설계:
  관계의 "존재"만 표현 ("이 상품이 이 나라에서 판매된다")
  주문량은 PostgreSQL orders_unified에서 집계 (정확하고 시계열 가능)
  Neo4j = "왜?"(인과 체인), PostgreSQL = "얼마나?"(집계)
"""

from dataclasses import dataclass

import structlog
from neo4j import Driver

logger = structlog.get_logger()

# 플랫폼 코드 → Neo4j Platform 노드 name 매핑
PLATFORM_MAP = {"cafe24": "Cafe24", "qoo10": "Qoo10", "shopee": "Shopee"}


@dataclass
class OrderContext:
    """graph_sync에 필요한 주문 컨텍스트.

    LLM이 추출하는 게 아니라, PostgreSQL 주문 데이터에서 가져오는 정보.
    이 정보가 있어야 Product 노드를 Country, Platform, ProductType에 연결할 수 있다.
    """

    order_id: str
    product_name: str
    product_type: str  # "sunscreen", "toner", ... — 주문 데이터에서 옴
    destination_country: str  # "JP", "SG", "KR" — 주문 데이터에서 옴
    platform: str  # "cafe24", "qoo10", "shopee" — 어떤 테이블에서 왔는지


class GraphSynchronizer:

    def __init__(self, driver: Driver):
        self.driver = driver

    def sync(self, order: OrderContext, attrs: dict) -> bool:
        """추출 결과를 Neo4j에 동기화.

        order: 주문 데이터에서 온 정보 (country, platform, product_type)
        attrs: LLM이 추출한 정보 (brand, keyIngredients, functionalClaims, ...)

        두 소스를 합쳐서 Product 노드 + 관계를 생성한다.

        Returns:
            True if any relationship was created (매칭된 온톨로지 노드가 있었음)
        """
        created_any = False

        with self.driver.session() as session:
            # ❶ Product 노드 생성 (NEW — 이전에 없었음)
            session.run(
                """
                MERGE (p:Product {id: $oid})
                SET p += $props
                """,
                oid=order.order_id,
                props={
                    "name": order.product_name,
                    "brand": attrs.get("brand", ""),
                    "productType": attrs.get("productType", ""),
                    "functionalClaims": attrs.get("functionalClaims", []),
                    "valueClaims": attrs.get("valueClaims", []),
                    "keyIngredients": attrs.get("keyIngredients", []),
                    "spf": attrs.get("spf"),
                    "pa": attrs.get("pa"),
                    "volume": attrs.get("volume"),
                },
            )

            # ❷ Brand 연결 — LLM 추출 결과 → 시드된 Brand 노드
            brand = attrs.get("brand")
            if brand:
                r = session.run(
                    """
                    MATCH (p:Product {id:$oid}),(b:Brand {name:$b})
                    MERGE (p)-[:MADE_BY]->(b)
                    RETURN b.name
                    """,
                    oid=order.order_id,
                    b=brand,
                )
                if r.single():
                    created_any = True

            # ❸ ProductType 연결 — 주문 데이터 → 시드된 ProductType 노드
            session.run(
                """
                MATCH (p:Product {id:$oid}),(t:ProductType {nameEn:$t})
                MERGE (p)-[:IS_TYPE]->(t)
                """,
                oid=order.order_id,
                t=order.product_type,
            )

            # ❹ 성분 연결 — LLM 추출 결과 → 시드된 Ingredient 노드
            #    MATCH로 "찾고", 있으면 관계 생성, 없으면 로그만
            for ingr_ko in attrs.get("keyIngredients", []):
                r = session.run(
                    """
                    MATCH (p:Product {id:$oid}),(i:Ingredient {commonNameKo:$i})
                    MERGE (p)-[:CONTAINS]->(i)
                    RETURN i.inciName
                    """,
                    oid=order.order_id,
                    i=ingr_ko,
                )
                if r.single():
                    created_any = True
                else:
                    # 매칭 실패 → 로그만 남기고 skip
                    logger.info(
                        "ingredient_not_in_ontology",
                        ingredient=ingr_ko,
                        order_id=order.order_id,
                    )

            # ❺ 국가 연결 — 주문 데이터 → 시드된 Country 노드
            #    관계 존재만 표현. 주문량은 PostgreSQL에서 집계.
            session.run(
                """
                MATCH (p:Product {id:$oid}),(c:Country {code:$c})
                MERGE (p)-[:SOLD_IN]->(c)
                """,
                oid=order.order_id,
                c=order.destination_country,
            )

            # ❻ 플랫폼 연결 — 주문 데이터 → 시드된 Platform 노드
            platform_name = PLATFORM_MAP.get(order.platform, order.platform)
            session.run(
                """
                MATCH (p:Product {id:$oid}),(pl:Platform {name:$pl})
                MERGE (p)-[:SOLD_ON]->(pl)
                """,
                oid=order.order_id,
                pl=platform_name,
            )

        logger.info(
            "graph_synced",
            order_id=order.order_id,
            brand=attrs.get("brand"),
            ingredients=attrs.get("keyIngredients", []),
            created_any=created_any,
        )
        return created_any
