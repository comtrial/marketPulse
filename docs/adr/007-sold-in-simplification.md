# ADR-007: SOLD_IN 관계에서 주문량 제거

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

초기 설계에서 Neo4j의 SOLD_IN 관계에 `totalOrders` 속성을 넣어서 "이 상품이 이 나라에서 몇 개 팔렸는지"를 같은 Cypher 쿼리 안에서 보려 했다.

```cypher
-- 초기 설계
MERGE (p)-[r:SOLD_IN]->(c)
ON CREATE SET r.totalOrders = $qty
ON MATCH SET r.totalOrders = r.totalOrders + $qty
```

## 결정

SOLD_IN은 관계의 "존재"만 표현한다. 주문량은 PostgreSQL에서 집계한다.

```cypher
-- 변경 후
MATCH (p:Product {id:$oid}), (c:Country {code:$c})
MERGE (p)-[:SOLD_IN]->(c)
```

## 근거

1. **정확한 집계가 안 됨**: 같은 상품이 10번 주문되면 totalOrders += 10이지만, "2026년 1월 일본에서 이 상품이 몇 개 팔렸는지"는? → 월별 데이터가 없음. 시계열 분석 불가.

2. **PostgreSQL에 이미 있음**: `orders_unified`에서 GROUP BY로 정확한 집계 가능. 월별, 국가별, 플랫폼별 자유자재.

3. **이중 저장의 일관성 문제**: "하나의 쿼리로"의 편의를 위해 데이터를 중복 저장하면 일관성 관리가 이중.

## 역할 분리 원칙

| DB | 역할 | 질문 |
|----|------|------|
| **Neo4j** | "왜?" | 인과 체인 (기후 → 피부고민 → 기능 → 성분 → 상품) |
| **PostgreSQL** | "얼마나?" | 집계 (비율, 주문량, 시계열) |

MCP 서버 2개가 각각을 래핑해서 LLM 오케스트레이터가 조합하는 구조에서, 이 분리가 자연스럽다.

## 결과

- **장점**: Neo4j에 불필요한 집계 데이터 없음, 일관성 단순화
- **장점**: graph_sync 코드 단순화 (ON CREATE/ON MATCH 분기 제거)
- **단점**: 인과 체인 + 판매량을 하나의 Cypher로 볼 수 없음
- **대안**: MCP 오케스트레이터가 Neo4j(인과) + PostgreSQL(집계)을 조합
