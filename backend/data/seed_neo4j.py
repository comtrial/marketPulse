"""Neo4j ontology seed — STEP 1~12 from Doc 2 spec.

Usage:
    cd backend && python -m data.seed_neo4j
    cd backend && python -m data.seed_neo4j --verify
"""

import argparse
import sys

import structlog

from core.config import settings
from core.neo4j_client import neo4j_driver

logger = structlog.get_logger()

# ── Cypher statements grouped by step ──────────────────────────────

CONSTRAINTS = [
    "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT ingredient_inci IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.inciName IS UNIQUE",
    "CREATE CONSTRAINT brand_id IF NOT EXISTS FOR (b:Brand) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT country_code IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS UNIQUE",
    "CREATE CONSTRAINT platform_id IF NOT EXISTS FOR (pl:Platform) REQUIRE pl.id IS UNIQUE",
    "CREATE CONSTRAINT function_id IF NOT EXISTS FOR (f:Function) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT concern_id IF NOT EXISTS FOR (s:SkinConcern) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT climate_type IF NOT EXISTS FOR (cz:ClimateZone) REQUIRE cz.type IS UNIQUE",
    "CREATE CONSTRAINT product_type_id IF NOT EXISTS FOR (t:ProductType) REQUIRE t.id IS UNIQUE",
    "CREATE INDEX product_name IF NOT EXISTS FOR (p:Product) ON (p.name)",
    "CREATE INDEX ingredient_ko IF NOT EXISTS FOR (i:Ingredient) ON (i.commonNameKo)",
]

STEP_01_COUNTRIES = [
    'CREATE (:Country {code: "KR", name: "South Korea", nameKo: "한국"})',
    'CREATE (:Country {code: "JP", name: "Japan", nameKo: "일본"})',
    'CREATE (:Country {code: "SG", name: "Singapore", nameKo: "싱가포르"})',
]

STEP_02_CLIMATES = [
    'CREATE (:ClimateZone {type: "온대_사계절", avgHumidity: "60-70%", avgTemp: "12C", uvIndex: "중간"})',
    'CREATE (:ClimateZone {type: "온대_고UV여름", avgHumidity: "65-80%", avgTemp: "16C", uvIndex: "높음"})',
    'CREATE (:ClimateZone {type: "열대_다습", avgHumidity: "80-90%", avgTemp: "28C", uvIndex: "극심"})',
    'MATCH (c:Country {code:"KR"}),(cz:ClimateZone {type:"온대_사계절"}) CREATE (c)-[:HAS_CLIMATE]->(cz)',
    'MATCH (c:Country {code:"JP"}),(cz:ClimateZone {type:"온대_고UV여름"}) CREATE (c)-[:HAS_CLIMATE]->(cz)',
    'MATCH (c:Country {code:"SG"}),(cz:ClimateZone {type:"열대_다습"}) CREATE (c)-[:HAS_CLIMATE]->(cz)',
]

STEP_03_CONCERNS = [
    'CREATE (:SkinConcern {id: "concern_uv", name: "UV_damage", nameKo: "자외선손상"})',
    'CREATE (:SkinConcern {id: "concern_oil", name: "excess_oil", nameKo: "과잉유분"})',
    'CREATE (:SkinConcern {id: "concern_dehydration", name: "dehydration", nameKo: "수분부족"})',
    'CREATE (:SkinConcern {id: "concern_sensitive", name: "sensitivity", nameKo: "민감성"})',
    'CREATE (:SkinConcern {id: "concern_dullness", name: "dullness", nameKo: "칙칙함"})',
]

STEP_04_TRIGGERS = [
    """MATCH (cz:ClimateZone {type:"온대_고UV여름"}),(sc:SkinConcern {id:"concern_uv"})
       CREATE (cz)-[:TRIGGERS {strength:0.88, season:"여름", mechanism:"높은 UV 지수로 피부 광손상"}]->(sc)""",
    # JP(온대_고UV여름)→dehydration 제거 — 커버리지 매트릭스에서 JP_lip 인과 공백 의도
    # """MATCH (cz:ClimateZone {type:"온대_고UV여름"}),(sc:SkinConcern {id:"concern_dehydration"})
    #    CREATE (cz)-[:TRIGGERS {strength:0.65, season:"겨울", mechanism:"건조한 겨울 공기로 경피 수분 손실"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"열대_다습"}),(sc:SkinConcern {id:"concern_oil"})
       CREATE (cz)-[:TRIGGERS {strength:0.90, season:"연중", mechanism:"고온 다습으로 피지 과다 분비"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"열대_다습"}),(sc:SkinConcern {id:"concern_dehydration"})
       CREATE (cz)-[:TRIGGERS {strength:0.82, season:"연중", mechanism:"에어컨 실내환경으로 역설적 탈수"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"열대_다습"}),(sc:SkinConcern {id:"concern_uv"})
       CREATE (cz)-[:TRIGGERS {strength:0.85, season:"연중", mechanism:"적도 근접으로 연중 강한 UV"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"온대_사계절"}),(sc:SkinConcern {id:"concern_uv"})
       CREATE (cz)-[:TRIGGERS {strength:0.70, season:"여름", mechanism:"여름 UV 및 미세먼지 복합 자극"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"온대_사계절"}),(sc:SkinConcern {id:"concern_dehydration"})
       CREATE (cz)-[:TRIGGERS {strength:0.75, season:"겨울", mechanism:"난방 건조로 피부 장벽 약화"}]->(sc)""",
    """MATCH (cz:ClimateZone {type:"온대_사계절"}),(sc:SkinConcern {id:"concern_sensitive"})
       CREATE (cz)-[:TRIGGERS {strength:0.60, season:"연중", mechanism:"미세먼지 등 환경 스트레스"}]->(sc)""",
]

STEP_05_FUNCTIONS = [
    'CREATE (:Function {id: "func_uv", name: "UV차단", category: "UV차단"})',
    'CREATE (:Function {id: "func_hydra", name: "수분공급", category: "보습"})',
    'CREATE (:Function {id: "func_sebo", name: "피지조절", category: "피지조절"})',
    'CREATE (:Function {id: "func_sooth", name: "진정", category: "진정"})',
    'CREATE (:Function {id: "func_bright", name: "브라이트닝", category: "브라이트닝"})',
    'CREATE (:Function {id: "func_antox", name: "항산화", category: "항산화"})',
]

STEP_06_DRIVES_DEMAND = [
    'MATCH (sc:SkinConcern {id:"concern_uv"}),(f:Function {id:"func_uv"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.92}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_uv"}),(f:Function {id:"func_antox"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.55}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_dehydration"}),(f:Function {id:"func_hydra"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.88}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_oil"}),(f:Function {id:"func_sebo"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.85}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_oil"}),(f:Function {id:"func_hydra"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.60}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_sensitive"}),(f:Function {id:"func_sooth"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.80}]->(f)',
    'MATCH (sc:SkinConcern {id:"concern_dullness"}),(f:Function {id:"func_bright"}) CREATE (sc)-[:DRIVES_DEMAND {strength:0.78}]->(f)',
]

STEP_07_INGREDIENTS = [
    'CREATE (:Ingredient {inciName:"NIACINAMIDE", commonNameKo:"나이아신아마이드", commonNameEn:"Niacinamide", origin:"합성"})',
    'CREATE (:Ingredient {inciName:"SODIUM_HYALURONATE", commonNameKo:"히알루론산", commonNameEn:"Hyaluronic Acid", origin:"발효"})',
    'CREATE (:Ingredient {inciName:"CENTELLA_ASIATICA_EXTRACT", commonNameKo:"센텔라", commonNameEn:"Centella Asiatica", origin:"천연"})',
    'CREATE (:Ingredient {inciName:"HOUTTUYNIA_CORDATA_EXTRACT", commonNameKo:"어성초", commonNameEn:"Houttuynia Cordata", origin:"천연"})',
    'CREATE (:Ingredient {inciName:"CAMELLIA_SINENSIS_LEAF_EXTRACT", commonNameKo:"녹차", commonNameEn:"Green Tea", origin:"천연"})',
    'CREATE (:Ingredient {inciName:"CERAMIDE_NP", commonNameKo:"세라마이드", commonNameEn:"Ceramide", origin:"합성"})',
    'CREATE (:Ingredient {inciName:"ZINC_OXIDE", commonNameKo:"징크옥사이드", commonNameEn:"Zinc Oxide", origin:"합성"})',
    'CREATE (:Ingredient {inciName:"SALICYLIC_ACID", commonNameKo:"살리실산", commonNameEn:"Salicylic Acid", origin:"합성"})',
    'CREATE (:Ingredient {inciName:"PROPOLIS_EXTRACT", commonNameKo:"프로폴리스", commonNameEn:"Propolis", origin:"천연"})',
    'CREATE (:Ingredient {inciName:"DAUCUS_CAROTA_SATIVA_ROOT_EXTRACT", commonNameKo:"당근", commonNameEn:"Carrot", origin:"천연"})',
]

STEP_08_HAS_FUNCTION = [
    'MATCH (i:Ingredient {inciName:"NIACINAMIDE"}),(f:Function {id:"func_bright"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"NIACINAMIDE"}),(f:Function {id:"func_sebo"}) CREATE (i)-[:HAS_FUNCTION {primary:false}]->(f)',
    'MATCH (i:Ingredient {inciName:"SODIUM_HYALURONATE"}),(f:Function {id:"func_hydra"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"CENTELLA_ASIATICA_EXTRACT"}),(f:Function {id:"func_sooth"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"HOUTTUYNIA_CORDATA_EXTRACT"}),(f:Function {id:"func_sooth"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"CAMELLIA_SINENSIS_LEAF_EXTRACT"}),(f:Function {id:"func_antox"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"CAMELLIA_SINENSIS_LEAF_EXTRACT"}),(f:Function {id:"func_sooth"}) CREATE (i)-[:HAS_FUNCTION {primary:false}]->(f)',
    'MATCH (i:Ingredient {inciName:"CERAMIDE_NP"}),(f:Function {id:"func_hydra"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"ZINC_OXIDE"}),(f:Function {id:"func_uv"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"SALICYLIC_ACID"}),(f:Function {id:"func_sebo"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"PROPOLIS_EXTRACT"}),(f:Function {id:"func_sooth"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
    'MATCH (i:Ingredient {inciName:"PROPOLIS_EXTRACT"}),(f:Function {id:"func_antox"}) CREATE (i)-[:HAS_FUNCTION {primary:false}]->(f)',
    'MATCH (i:Ingredient {inciName:"DAUCUS_CAROTA_SATIVA_ROOT_EXTRACT"}),(f:Function {id:"func_antox"}) CREATE (i)-[:HAS_FUNCTION {primary:true}]->(f)',
]

STEP_09_SYNERGIES = [
    """MATCH (a:Ingredient {inciName:"NIACINAMIDE"}),(b:Ingredient {inciName:"SODIUM_HYALURONATE"})
       CREATE (a)-[:SYNERGIZES_WITH {mechanism:"나이아신아마이드가 히알루론산의 수분 유지를 보조"}]->(b)""",
    """MATCH (a:Ingredient {inciName:"CENTELLA_ASIATICA_EXTRACT"}),(b:Ingredient {inciName:"CAMELLIA_SINENSIS_LEAF_EXTRACT"})
       CREATE (a)-[:SYNERGIZES_WITH {mechanism:"센텔라+녹차의 진정+항산화 복합 효과"}]->(b)""",
    """MATCH (a:Ingredient {inciName:"CERAMIDE_NP"}),(b:Ingredient {inciName:"SODIUM_HYALURONATE"})
       CREATE (a)-[:SYNERGIZES_WITH {mechanism:"세라마이드가 장벽을 복구하고 히알루론산이 수분을 채움"}]->(b)""",
]

STEP_10_PLATFORMS = [
    'CREATE (:Platform {id:"plat_cafe24", name:"Cafe24", countries:["KR","JP","SG"]})',
    'CREATE (:Platform {id:"plat_qoo10", name:"Qoo10", countries:["JP","SG"]})',
    'CREATE (:Platform {id:"plat_shopee", name:"Shopee", countries:["SG"]})',
]

STEP_11_PRODUCT_TYPES = [
    'CREATE (:ProductType {id:"type_sunscreen", name:"선크림", nameEn:"sunscreen", parentType:"선케어"})',
    'CREATE (:ProductType {id:"type_toner", name:"토너", nameEn:"toner", parentType:"스킨케어"})',
    'CREATE (:ProductType {id:"type_serum", name:"세럼", nameEn:"serum", parentType:"스킨케어"})',
    'CREATE (:ProductType {id:"type_cream", name:"크림", nameEn:"cream", parentType:"스킨케어"})',
    'CREATE (:ProductType {id:"type_lip", name:"립", nameEn:"lip", parentType:"메이크업"})',
]

STEP_12_BRANDS = [
    'CREATE (:Brand {id:"brand_innisfree", name:"이니스프리", nameEn:"Innisfree", country:"KR"})',
    'CREATE (:Brand {id:"brand_torriden", name:"토리든", nameEn:"Torriden", country:"KR"})',
    'CREATE (:Brand {id:"brand_roundlab", name:"라운드랩", nameEn:"Roundlab", country:"KR"})',
    'CREATE (:Brand {id:"brand_skinfood", name:"스킨푸드", nameEn:"Skinfood", country:"KR"})',
]

ALL_STEPS = [
    ("Constraints & Indexes", CONSTRAINTS),
    ("STEP 01: Countries", STEP_01_COUNTRIES),
    ("STEP 02: ClimateZones + links", STEP_02_CLIMATES),
    ("STEP 03: SkinConcerns", STEP_03_CONCERNS),
    ("STEP 04: TRIGGERS (Climate→Concern)", STEP_04_TRIGGERS),
    ("STEP 05: Functions", STEP_05_FUNCTIONS),
    ("STEP 06: DRIVES_DEMAND (Concern→Function)", STEP_06_DRIVES_DEMAND),
    ("STEP 07: Ingredients", STEP_07_INGREDIENTS),
    ("STEP 08: HAS_FUNCTION (Ingredient→Function)", STEP_08_HAS_FUNCTION),
    ("STEP 09: SYNERGIZES_WITH", STEP_09_SYNERGIES),
    ("STEP 10: Platforms", STEP_10_PLATFORMS),
    ("STEP 11: ProductTypes", STEP_11_PRODUCT_TYPES),
    ("STEP 12: Brands", STEP_12_BRANDS),
]


def seed() -> None:
    with neo4j_driver.session() as session:
        # Clean existing data
        session.run("MATCH (n) DETACH DELETE n")
        logger.info("cleared_existing_data")

        for step_name, queries in ALL_STEPS:
            for q in queries:
                session.run(q)
            logger.info("step_completed", step=step_name, queries=len(queries))

    logger.info("seed_complete")


def verify() -> None:
    with neo4j_driver.session() as session:
        # Node counts
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
        )
        print("\n=== Node Counts ===")
        total_nodes = 0
        for record in result:
            print(f"  {record['label']}: {record['count']}")
            total_nodes += record["count"]
        print(f"  TOTAL: {total_nodes}")

        # Relationship counts
        result = session.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY type"
        )
        print("\n=== Relationship Counts ===")
        total_rels = 0
        for record in result:
            print(f"  {record['type']}: {record['count']}")
            total_rels += record["count"]
        print(f"  TOTAL: {total_rels}")

        # Causal chain test (Japan)
        result = session.run("""
            MATCH (c:Country {code:"JP"})-[:HAS_CLIMATE]->(cz)
                  -[t:TRIGGERS]->(sc)-[d:DRIVES_DEMAND]->(f)
                  <-[:HAS_FUNCTION]-(i:Ingredient)
            WHERE t.strength > 0.5 AND d.strength > 0.5
            RETURN sc.nameKo AS concern, f.name AS func,
                   i.commonNameKo AS ingredient,
                   round(t.strength * d.strength * 100)/100.0 AS chain_strength
            ORDER BY chain_strength DESC
        """)
        print("\n=== Causal Chain: Japan ===")
        for record in result:
            print(
                f"  {record['concern']} → {record['func']} → "
                f"{record['ingredient']} (strength: {record['chain_strength']})"
            )

    print("\nVerification complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="Run verification queries only")
    args = parser.parse_args()

    if args.verify:
        verify()
    else:
        seed()
        verify()
