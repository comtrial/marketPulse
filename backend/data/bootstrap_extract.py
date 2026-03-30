"""One-off 스크립트: 규칙 기반 속성 추출 → extractions 테이블 + Neo4j graph_sync.

generate_orders.py가 만든 상품명 패턴을 이미 알고 있으므로,
LLM 호출 없이 규칙 기반으로 속성을 추출하고 전체 파이프라인을 채운다.

이 스크립트는 최초 데이터 부트스트랩 용도이며, 이후 실제 추출은 extractor.py(LLM)를 사용한다.

Usage:
    cd backend && python -m data.bootstrap_extract
    cd backend && python -m data.bootstrap_extract --verify
    cd backend && python -m data.bootstrap_extract --clean  (기존 데이터 삭제 후 재실행)
"""

import argparse
import json
import re
import uuid

import structlog
from sqlalchemy import create_engine, text

from core.config import settings
from core.neo4j_client import neo4j_driver
from extraction.graph_sync import GraphSynchronizer, OrderContext

logger = structlog.get_logger()

ENGINE = create_engine(settings.database_url_sync)

# ── 브랜드명 매핑 (영문 → 한글) ──
BRAND_MAP = {
    "Innisfree": "이니스프리",
    "Torriden": "토리든",
    "Roundlab": "라운드랩",
    "Skinfood": "스킨푸드",
}

# ── 성분 키워드 → commonNameKo 매핑 ──
# 상품명에 포함된 키워드로 성분을 감지한다
INGREDIENT_PATTERNS = {
    "히알루론산": "히알루론산",
    "히알루론": "히알루론산",
    "센텔라": "센텔라",
    "시카": "센텔라",
    "나이아신아마이드": "나이아신아마이드",
    "녹차": "녹차",
    "그린티": "녹차",
    "세라마이드": "세라마이드",
    "징크옥사이드": "징크옥사이드",
    "살리실산": "살리실산",
    "프로폴리스": "프로폴리스",
    "당근": "당근",
    "캐롯": "당근",
    "카로틴": "당근",
    "어성초": "어성초",
}

# ── 기능 클레임 키워드 ──
# 원칙: 상품명의 키워드를 그대로 저장한다.
# "톤업"→"브라이트닝" 같은 동의어 변환은 추출 단계에서 하지 않는다.
# 상위 카테고리 매핑(톤업 ∈ 브라이트닝)은 집계 단계에서 별도 처리.
FUNC_PATTERNS = {
    "UV차단": ["SPF", "PA+", "선크림", "선스크린", "자외선", "UV"],
    "수분공급": ["수분", "보습"],
    "진정": ["진정", "카밍"],
    "톤업": ["톤업"],
    "미백": ["미백"],
    "노세범": ["노세범"],
    "피지조절": ["피지"],
    "항산화": ["항산화"],
    "피부장벽": ["피부장벽", "장벽"],
}

# ── 가치 클레임 키워드 ──
# 상품명에 명시적으로 표현된 가치 주장만 매핑.
VALUE_PATTERNS = {
    "비건": ["비건"],
    "저자극": ["저자극", "마일드"],
    "무향": ["무향"],
    "약산성": ["약산성"],
    "워터프루프": ["워터프루프"],
    "대용량": ["대용량"],
    "동물실험프리": ["동물실험프리"],
}


def extract_attrs(product_name: str, product_type: str, brand_en: str) -> dict:
    """상품명에서 규칙 기반으로 속성을 추출.

    generate_orders.py의 상품명 패턴을 알고 있으므로
    키워드 매칭만으로 정확한 추출이 가능하다.
    """
    name = product_name
    brand_ko = BRAND_MAP.get(brand_en, brand_en)

    # 성분 추출
    ingredients = []
    seen = set()
    for keyword, normalized in INGREDIENT_PATTERNS.items():
        if keyword in name and normalized not in seen:
            ingredients.append(normalized)
            seen.add(normalized)

    # sunscreen 기본 성분 매핑: 상품명에 성분이 없어도 카테고리 특성으로 추론
    # 실제 LLM 추출에서는 gold example의 few-shot을 보고 이런 추론을 수행함.
    # bootstrap은 규칙 기반이므로 명시적으로 보완.
    if product_type == "sunscreen" and not ingredients:
        # 무기자차 → 징크옥사이드 (주요 UV 차단 성분)
        if "무기자차" in name:
            ingredients.append("징크옥사이드")
            seen.add("징크옥사이드")

    # 기능 클레임 추출
    func_claims = []
    for claim, keywords in FUNC_PATTERNS.items():
        if any(kw in name for kw in keywords):
            func_claims.append(claim)

    # 선크림이면 UV차단 기본 추가
    if product_type == "sunscreen" and "UV차단" not in func_claims:
        func_claims.insert(0, "UV차단")

    # 가치 클레임 추출
    value_claims = []
    for claim, keywords in VALUE_PATTERNS.items():
        if any(kw in name for kw in keywords):
            value_claims.append(claim)

    # SPF/PA 추출
    spf = None
    pa = None
    spf_match = re.search(r"SPF(\d+\+?)", name)
    if spf_match:
        spf = spf_match.group(1)
    pa_match = re.search(r"PA(\++)", name)
    if pa_match:
        pa = pa_match.group(1)

    # 용량 추출
    volume = None
    vol_match = re.search(r"(\d+(?:\.\d+)?(?:ml|g|매))", name)
    if vol_match:
        volume = vol_match.group(1)

    # productType 한글 매핑
    type_ko_map = {
        "sunscreen": "선크림",
        "toner": "토너",
        "serum": "세럼",
        "cream": "크림",
        "lip": "립",
    }
    product_type_ko = type_ko_map.get(product_type, product_type)

    # additionalAttrs
    additional = {}
    if "무기자차" in name:
        additional["자차타입"] = "무기자차"
    if "마이크로바이옴" in name:
        additional["트렌드성분"] = "마이크로바이옴"
    if "유산균" in name:
        additional["트렌드성분"] = "마이크로바이옴"

    # 립 컬러/텍스처
    color_match = re.search(r"(#\d+ \S+)", name)
    if color_match and product_type == "lip":
        additional["컬러"] = color_match.group(1)
    for texture in ["매트", "글로시", "벨벳", "시어", "코튼잉크"]:
        if texture in name and product_type == "lip":
            additional["텍스처"] = texture

    attrs = {
        "productType": product_type_ko,
        "brand": brand_ko,
        "keyIngredients": ingredients,
        "functionalClaims": list(dict.fromkeys(func_claims)),  # 중복 제거, 순서 유지
        "valueClaims": value_claims,
        "spf": spf,
        "pa": pa,
        "volume": volume,
        "additionalAttrs": additional,
    }

    return attrs


def clean():
    """기존 extractions + Neo4j Product 노드 삭제."""
    with ENGINE.connect() as conn:
        conn.execute(text("DELETE FROM extractions"))
        conn.commit()
    logger.info("extractions_table_cleared")

    with neo4j_driver.session() as session:
        result = session.run("MATCH (p:Product) DETACH DELETE p RETURN count(p) AS cnt")
        cnt = result.single()["cnt"]
    logger.info("neo4j_products_deleted", count=cnt)


def bootstrap():
    """전체 주문 데이터에 대해 규칙 기반 추출 → extractions INSERT + graph_sync."""
    syncer = GraphSynchronizer(driver=neo4j_driver)

    with ENGINE.connect() as conn:
        result = conn.execute(text("""
            SELECT order_id, order_date, platform, destination_country,
                   brand, product_name, product_type, quantity, unit_price_usd
            FROM orders_unified
            ORDER BY order_date
        """))
        orders = result.mappings().all()

    logger.info("orders_loaded", count=len(orders))

    synced_count = 0
    total_count = 0

    with ENGINE.connect() as conn:
        for order in orders:
            attrs = extract_attrs(
                product_name=order["product_name"],
                product_type=order["product_type"],
                brand_en=order["brand"],
            )

            # extractions 테이블 INSERT
            extraction_id = str(uuid.uuid4())
            conn.execute(
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
                         0, 0, 0, 0,
                         true, null,
                         :synced)
                """),
                {
                    "eid": extraction_id,
                    "oid": order["order_id"],
                    "platform": order["platform"],
                    "attrs": json.dumps(attrs, ensure_ascii=False),
                    "sim": 1.0,  # 규칙 기반이므로 유사도 100%
                    "examples": [],
                    "synced": True,
                },
            )

            # graph_sync
            order_ctx = OrderContext(
                order_id=order["order_id"],
                product_name=order["product_name"],
                product_type=order["product_type"],
                destination_country=order["destination_country"],
                platform=order["platform"],
            )
            try:
                created = syncer.sync(order_ctx, attrs)
                if created:
                    synced_count += 1
            except Exception as e:
                logger.error("graph_sync_error", order_id=order["order_id"], error=str(e))

            total_count += 1
            if total_count % 100 == 0:
                conn.commit()
                logger.info("progress", processed=total_count, total=len(orders))

        conn.commit()

    logger.info(
        "bootstrap_complete",
        total=total_count,
        synced=synced_count,
    )


def verify():
    """부트스트랩 결과 검증."""
    with ENGINE.connect() as conn:
        # extractions 통계
        result = conn.execute(text("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE validation_passed = true) AS passed,
                   count(*) FILTER (WHERE graph_synced = true) AS synced
            FROM extractions
        """))
        row = result.mappings().one()
        print(f"\n=== Extractions ===")
        print(f"  Total: {row['total']}")
        print(f"  Validation passed: {row['passed']}")
        print(f"  Graph synced: {row['synced']}")

        # 속성별 분포
        result = conn.execute(text("""
            SELECT
                attributes->>'productType' AS ptype,
                count(*) AS cnt
            FROM extractions
            GROUP BY 1
            ORDER BY cnt DESC
        """))
        print(f"\n=== Product Type Distribution ===")
        for r in result.mappings():
            print(f"  {r['ptype']}: {r['cnt']}")

        # 성분 빈도 top 10
        result = conn.execute(text("""
            SELECT ingredient, count(*) AS cnt
            FROM extractions,
                 jsonb_array_elements_text(attributes->'keyIngredients') AS ingredient
            GROUP BY ingredient
            ORDER BY cnt DESC
            LIMIT 10
        """))
        print(f"\n=== Top 10 Ingredients ===")
        for r in result.mappings():
            print(f"  {r['ingredient']}: {r['cnt']}")

        # 기능 클레임 빈도
        result = conn.execute(text("""
            SELECT claim, count(*) AS cnt
            FROM extractions,
                 jsonb_array_elements_text(attributes->'functionalClaims') AS claim
            GROUP BY claim
            ORDER BY cnt DESC
        """))
        print(f"\n=== Functional Claims ===")
        for r in result.mappings():
            print(f"  {r['claim']}: {r['cnt']}")

    # Neo4j 검증
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label
        """)
        print(f"\n=== Neo4j Node Counts ===")
        for record in result:
            print(f"  {record['label']}: {record['count']}")

        result = session.run("""
            MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY type
        """)
        print(f"\n=== Neo4j Relationship Counts ===")
        for record in result:
            print(f"  {record['type']}: {record['count']}")

        # 인과 체인 + 실데이터 쿼리
        result = session.run("""
            MATCH (c:Country {code:"JP"})-[:HAS_CLIMATE]->(cz)
                  -[t:TRIGGERS]->(sc)-[d:DRIVES_DEMAND]->(f)
                  <-[:HAS_FUNCTION]-(i:Ingredient)
                  <-[:CONTAINS]-(p:Product)-[:SOLD_IN]->(c)
            WHERE t.strength > 0.6 AND d.strength > 0.6
            RETURN i.commonNameKo AS ingredient, count(DISTINCT p) AS products,
                   round(t.strength * d.strength * 100)/100.0 AS chain_strength
            ORDER BY products DESC
            LIMIT 5
        """)
        print(f"\n=== Causal Chain + Real Data: Japan ===")
        for record in result:
            print(
                f"  {record['ingredient']}: "
                f"{record['products']} products "
                f"(chain: {record['chain_strength']})"
            )

    print("\nVerification complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="검증만 실행")
    parser.add_argument("--clean", action="store_true", help="기존 데이터 삭제 후 재실행")
    args = parser.parse_args()

    if args.verify:
        verify()
    elif args.clean:
        clean()
        bootstrap()
        verify()
    else:
        bootstrap()
        verify()
