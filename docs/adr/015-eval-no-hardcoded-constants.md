# ADR-015: Eval 메트릭에서 상수 하드코딩 제거 — Neo4j에서 동적 조회

- **상태**: accepted
- **날짜**: 2026-03-30

## 맥락

Eval 프레임워크의 축 3(추론 커버리지)에서 국가×유형 매트릭스를 구성할 때, 국가 코드(`["KR", "JP", "SG"]`)와 제품 유형(`["sunscreen", "toner", ...]`)이 필요하다. 초기 구현에서 이를 Python 상수로 하드코딩했다.

## 문제

```python
# 하드코딩
COUNTRIES = ["KR", "JP", "SG"]
PRODUCT_TYPES = ["sunscreen", "toner", "serum", "cream", "lip"]
PRODUCT_TYPE_KO = {"sunscreen": "선크림", ...}
```

- 시드 데이터에 국가/유형이 추가되면 eval 코드도 수정해야 함
- Neo4j에 이미 `Country`, `ProductType` 노드가 존재하는데 중복 관리
- Phase 2에서 새 국가/유형이 들어오면 코드 변경 없이 반영되어야 함

## 결정

**Eval 메트릭에서 국가/유형 목록을 Neo4j에서 동적으로 조회한다.**

```python
def _get_countries(driver) -> list[str]:
    return neo4j.query("MATCH (c:Country) RETURN c.code")

def _get_product_types(driver) -> list[dict]:
    return neo4j.query("MATCH (t:ProductType) RETURN t.nameEn, t.name")
```

## 근거

1. **단일 진실 소스**: Neo4j의 `Country`/`ProductType` 노드가 원본. eval이 이를 참조.
2. **확장 무비용**: 새 국가(`TW`)나 유형(`mask`)을 Neo4j에 시드하면 eval 매트릭스가 자동 확장.
3. **일관성**: seed_neo4j.py → Neo4j → eval/metrics.py 의 한 방향 흐름. 중간에 Python 상수가 끼어들지 않음.
4. **Neo4j 호출 오버헤드**: 국가 3개 + 유형 5개 조회는 ~2ms. eval 실행 시 1회만 호출하므로 무시 가능.

## 적용

- `eval/metrics.py`: `_get_countries(driver)`, `_get_product_types(driver)` 헬퍼 함수
- `eval_reasoning_coverage()`에서 동적 조회 후 매트릭스 구성
- 같은 원칙을 향후 다른 모듈에서도 적용 (bootstrap_extract, order_server 등의 상수도 점진적 교체 대상)

## 결과

- **장점**: 시드 변경 시 eval 코드 수정 불필요
- **장점**: "왜 이 3개국인가?"에 대한 답이 코드가 아닌 데이터
- **단점**: Neo4j 연결이 필요 (eval 실행 시 Neo4j가 떠있어야 함)
- **후속**: bootstrap_extract.py의 `BRAND_MAP` 등도 같은 원칙으로 교체 검토
