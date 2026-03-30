# MarketPulse

**Cross-Border Ecommerce 실 주문 데이터 기반 K-Beauty 인텔리전스 시스템**

역직구 뷰티 상품의 비정형 속성을 구조화하고, Neo4j 인과 체인 위에 실 데이터를 배치하여, LLM이 자율적으로 데이터 소스를 조합해 셀러에게 인사이트를 제공한다.

<!-- 스크린샷: 대시보드 전체 화면 — Zone A 접힌 상태, Zone B에 차트+인과체인+LLM분석, Zone C에 ReAct 트레이스 -->

---

## 목차

- [문제 정의](#문제-정의)
- [기술적 접근과 설계 결정](#기술적-접근과-설계-결정)
- [시스템 아키텍처](#시스템-아키텍처)
- [핵심 파이프라인 1: 속성 추출](#핵심-파이프라인-1-속성-추출)
- [핵심 파이프라인 2: 인텔리전스 오케스트레이터](#핵심-파이프라인-2-인텔리전스-오케스트레이터)
- [핵심 파이프라인 3: PatternScout — 자율 패턴 탐지](#핵심-파이프라인-3-patternscout--자율-패턴-탐지)
- [Eval 프레임워크: Knowledge Growth 측정](#eval-프레임워크-knowledge-growth-측정)
- [엔지니어링 결정 기록 (ADR)](#엔지니어링-결정-기록-adr)
- [한계점과 향후 계획](#한계점과-향후-계획)
- [기술 스택](#기술-스택)
- [실행 방법](#실행-방법)

---

## 문제 정의

### 도메인 컨텍스트

크로스보더 이커머스(역직구)에서 화장품/뷰티 화주의 실 주문 데이터는 운영에만 쓰이고 있다. 국가별·채널별·속성별로 풍부한 시장 인사이트가 묻혀 있는데, 이를 꺼내려면 **비정형 상품명에서 구조화된 속성을 추출**해야 한다.

### 왜 기존 방법으로 안 되는가

**룰 기반의 한계** — "비건"은 키워드로 잡히지만, "무기자차"가 자외선 차단 방식인지, "77"이 성분 함량인지 모델 번호인지, "약산성"이 pH 특성인지 마케팅 문구인지는 맥락 의존적이다. 더 근본적으로, 하위 카테고리마다 의미 있는 속성이 다르고(선크림의 "무기자차"는 토너에서 무의미), 신규 트렌드("마이크로바이옴")가 계속 등장해서 속성 사전을 하드코딩할 수 없다.

**LLM(zero-shot)의 한계** — 개별 추출은 80점짜리를 하지만, 1,000건을 추출하면 키 이름이 제각각("주요성분" vs "key_ingredient" vs "ingredients")이라 `GROUP BY`가 안 된다. **Dynamic Few-Shot의 진짜 가치는 개별 정확도 향상이 아니라, 대규모 집계를 위한 스키마 일관성 강제**다.

**단순 SQL 집계의 한계** — "일본에서 비건 비율이 58%"라는 숫자는 나오지만, "왜 58%인가?"는 답할 수 없다. "일본의 여름 고UV → UV 손상 우려 → 클린뷰티 트렌드와 맞물려 비건 선크림 수요 급증"이라는 **인과 체인**을 도출하려면 온톨로지 기반의 지식 그래프가 필요하다.

---

## 기술적 접근과 설계 결정

### 접근 1: Tool Use + Dynamic Few-Shot — 2레이어 스키마 강제

LLM 1회 호출로 비정형 상품명에서 구조화된 속성을 추출한다. LangChain을 사용하지 않고 Anthropic SDK로 직접 구현.

```
Tool Use  → 구조 강제. "functionalClaims"이 항상 string[]로 나오는 것을 보장.
Few-Shot  → 값 형식 유도. "어성초 추출물"이 아닌 "어성초"로 쓰도록 유도.
```

검토했으나 채택하지 않은 대안:
- **Tool Use만** → 구조는 해결되지만, 새 카테고리 추가 시 Tool description 수정 필요. Few-Shot은 gold example만 추가하면 되므로 코드 변경 없음(flywheel).
- **Few-Shot만** → 구조(키, 타입) 보장 불가. JSON Schema 강제가 없으면 1,000건 집계 시 스키마 드리프트.
- **카테고리 사전 분류 LLM 호출** → 벡터 검색이 암묵적으로 해결(토너 입력 → 토너 사례 상위). 별도 분류 호출은 비용 2배, 분류 오류 시 더 나빠짐. 제거.
- **Multi-Turn 자기 검증** → 외부 피드백 없는 self-correction은 효과 제한적. 환각은 규칙 기반 검증으로, 누락은 Eval로 커버. 비용 2배인데 품질 향상 미미. 제거.

### 접근 2: Neo4j 온톨로지 — 인과 체인이 "왜?"에 답한다

SQL 집계로는 "비건 58%"라는 숫자만 나온다. "왜?"에 답하려면 `Country → ClimateZone → SkinConcern → Function → Ingredient`로 이어지는 인과 체인이 필요하다.

```
[추상 계층 — 도메인 지식 시드]
  Japan →HAS_CLIMATE→ 온대_고UV여름 →TRIGGERS(0.88)→ UV손상
    →DRIVES_DEMAND(0.92)→ UV차단 ←HAS_FUNCTION← 징크옥사이드

[물리적 데이터 — 추출 시 자동 생성]
  Product(C24-001) →CONTAINS→ 징크옥사이드
  Product(C24-001) →SOLD_IN→ Japan

→ 하나의 Cypher로 "일본에서 실제로 팔리는 상품 중 인과 체인 정렬된 것" 조회
```

검토했으나 채택하지 않은 대안:
- **PostgreSQL JSON** → 5개 테이블 JOIN으로 인과 체인 표현 가능하지만 복잡. 새 관계 추가 시 JOIN 변경.
- **SOLD_IN에 주문량 누적** → Neo4j에 집계 데이터를 넣으면 월별 시계열 불가. **Neo4j = "왜?"(인과), PostgreSQL = "얼마나?"(집계)** 역할 분리 원칙 확립.

### 접근 3: LLM 오케스트레이터 — 도구 자율 선택

셀러의 질문에 따라 Neo4j(인과) + PostgreSQL(집계)을 LLM이 자율적으로 조합한다. while-loop ReAct 패턴으로 Anthropic SDK 직접 구현.

```
질문: "일본에서 비건이 왜 상승 중인지 분석해줘"

Step 1: LLM 사고 — "비율 추이를 먼저 확인하겠습니다"
        → get_attribute_trend (PostgreSQL) → JP 비건: 19%→56%
Step 2: LLM 사고 — "상승 확인됨. 인과 근거를 찾겠습니다"
        → query_causal_chain (Neo4j) → UV손상(0.88)→UV차단(0.92)
Step 3: LLM 종합 — 수치 + 인과를 조합하여 셀러 인사이트 생성
```

모든 step의 reasoning(사고) + decision(도구 선택) + result(결과)가 `tool_call_traces`에 기록되어, 왜 이 도구를 선택했는지 추적 가능.

<!-- 스크린샷: Zone C — ReAct 트레이스. Step 1(PostgreSQL, 파랑), Step 2(Neo4j, 녹색), Step 3(최종 답변)이 보이는 상태 -->

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        사용자 질문                               │
│                            │                                    │
│                            ▼                                    │
│                  ┌─── LLM 오케스트레이터 ───┐                    │
│                  │   (ReAct while-loop)     │                    │
│                  │   도구 자율 선택 + 로깅   │                    │
│                  └──┬────────────────┬──────┘                    │
│                     │                │                           │
│          ┌──────────▼─────┐  ┌──────▼──────────┐                │
│          │  KG Server     │  │  Order Server    │                │
│          │  (Neo4j)       │  │  (PostgreSQL)    │                │
│          │  "왜?"         │  │  "얼마나?"       │                │
│          │                │  │                  │                │
│          │  인과 체인      │  │  월별 트렌드     │                │
│          │  성분 시너지    │  │  속성 히트맵     │                │
│          │  상품 그래프    │  │  비율 집계       │                │
│          └────────────────┘  └─────────────────┘                │
│                     │                │                           │
│                     ▼                ▼                           │
│          ┌─────────────────────────────────┐                    │
│          │    tool_call_traces             │                    │
│          │    (판단 근거 + 비용 추적)       │                    │
│          └─────────────────────────────────┘                    │
│                                                                 │
│  ─── 속성 추출 (별도 파이프라인) ───                              │
│                                                                 │
│  상품명 → ChromaDB 벡터 검색 → LLM(Tool Use + Few-Shot)         │
│         → 규칙 기반 검증 → PostgreSQL 적재 + Neo4j graph_sync    │
└─────────────────────────────────────────────────────────────────┘
```

### 데이터 소스 역할 분리

| DB | 역할 | 답하는 질문 | 왜 이 DB인가 |
|----|------|-----------|------------|
| **Neo4j** | 온톨로지 + 인과 체인 | "왜?" | 관계 탐색 O(1) hop, 새 인과 관계 추가해도 기존 쿼리 불변 |
| **PostgreSQL** | 주문 데이터 + 집계 | "얼마나?" | DATE_TRUNC + GROUP BY, JSONB 속성 필터링 |
| **ChromaDB** | 벡터 검색 | "비슷한 사례?" | few-shot example 검색, cosine similarity |

---

## 핵심 파이프라인 1: 속성 추출

### 파이프라인 흐름 (LLM 1회 호출)

```
상품명: "토리든 다이브인 무기자차 선크림 SPF50+ PA++++ 60ml 비건"
    │
    ▼
[벡터 검색] ChromaDB에서 유사 gold example top-3
    │  intfloat/multilingual-e5-large (1024차원)
    │  정렬: cosine_similarity × 0.7 + attribute_richness × 0.3
    │  (속성이 풍부한 예시를 우선 → LLM이 더 많은 속성을 추출하게 유도)
    │
    ▼
[LLM 추출] Claude + Tool Use 강제 + system prompt에 few-shot 주입
    │  tool_choice: forced → 반드시 Tool 호출 (텍스트 응답 불가)
    │  → {productType: "선크림", brand: "토리든", keyIngredients: ["히알루론산", "징크옥사이드"],
    │      functionalClaims: ["UV차단"], valueClaims: ["비건"], spf: "50+", pa: "++++", ...}
    │
    ▼
[규칙 기반 검증] LLM 호출 없음
    │  errors (graph_sync 차단): 필수필드 누락, 타입 오류, SPF 범위, PA 형식
    │  warnings (통과하되 로그): 성분 환각 의심, SPF 환각, 교차 의심(토너+SPF)
    │  (교차 검증이 error가 아닌 warning인 이유: 크림+SPF가 실제로 존재하므로)
    │
    ▼
[적재 + graph_sync]
    errors 없음 → extractions INSERT + Neo4j Product 노드 + 관계 생성
    errors 있음 → extractions INSERT만 (graph_sync 안 함)
```

### 설계 결정: 왜 Confidence 모듈을 제거했는가

초기 설계에서는 `similarity × 0.5 + validation × 0.3 + richness × 0.2`로 confidence tier를 분류하려 했다. 제거한 이유:
1. **가중치의 근거 부재** — 왜 similarity가 50%인지 설명 불가. 설명 불가능한 점수는 운영에서 쓸모없다.
2. **MVP에서 운영 시나리오 없음** — 1,000건 배치 처리에서 "이건 자동 승인, 저건 검수"를 분류할 필요가 없다.
3. **validator 판단으로 충분** — errors 없으면 graph_sync, 있으면 안 함. 이 이분법이 MVP에서 필요한 전부.

### 설계 결정: 추출 시 원본 키워드 보존 원칙

"톤업"을 "브라이트닝"으로, "노세범"을 "피지조절"로 동의어 변환하면 `get_attribute_trend("톤업")`으로 검색 시 0건이 반환된다. 추출 단계에서는 상품명의 키워드를 그대로 저장하고, 상위 카테고리 매핑(톤업 ∈ 브라이트닝)은 집계 단계에서 별도 처리한다. 정보 손실 방지 + LLM 추출과의 형식 일관성.

### graph_sync: 추상 계층 위에 물리적 데이터를 올려놓는 과정

```
주문 데이터에서 오는 것:  country("JP"), platform("cafe24"), product_type("sunscreen")
LLM이 추출하는 것:       brand("토리든"), keyIngredients(["히알루론산"]), valueClaims(["비건"])

graph_sync가 하는 일:
  ❶ Product 노드 생성 (NEW)
  ❷ Product →MADE_BY→ Brand(토리든)     ← LLM 추출
  ❸ Product →CONTAINS→ Ingredient(히알루론산) ← LLM 추출
  ❹ Product →SOLD_IN→ Country(JP)       ← 주문 데이터
  ❺ Product →IS_TYPE→ ProductType(sunscreen) ← 주문 데이터

→ 시드된 온톨로지(39노드) + graph_sync된 실데이터(1,000 Product)
  = 인과 체인 + 실 상품이 하나의 Cypher로 조회 가능
```

---

## 핵심 파이프라인 2: 인텔리전스 오케스트레이터

### 도구 8개 — Pydantic 기반 스키마 자동 생성

수동으로 300줄짜리 JSON 스키마를 쓰는 대신, 각 도구의 입력을 Pydantic `BaseModel`로 정의하고 `@tool` 데코레이터를 부착한다. `model_json_schema()`가 Anthropic Tool의 `input_schema`를 자동 생성하고, 함수의 docstring이 `description`이 된다.

```python
class QueryCausalChainInput(BaseModel):
    country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")

@tool(QueryCausalChainInput)
def query_causal_chain(self, params: QueryCausalChainInput) -> list[dict]:
    """특정 국가의 기후→피부고민→기능 수요 인과 체인을 반환."""
    ...
```

도구를 추가할 때 서버 파일 1곳만 수정. 오케스트레이터 코드 변경 불필요(단일 수정 지점 원칙). 런타임에 Pydantic이 입력을 검증하여 LLM이 잘못된 파라미터를 보내면 조기 감지.

| 서버 | 도구 | DB | 역할 |
|------|------|-----|------|
| KG Server | `query_causal_chain` | Neo4j | 기후→피부고민→기능 인과 체인 |
| KG Server | `find_trending_ingredients` | Neo4j | 국가별 성분 상품 등장 빈도 |
| KG Server | `get_product_graph` | Neo4j | 상품의 전체 그래프 컨텍스트 |
| KG Server | `find_ingredient_synergies` | Neo4j | 명시적 시너지 + co-occurrence |
| Order Server | `get_attribute_trend` | PostgreSQL | 속성별 월별 비율 시계열 |
| Order Server | `get_country_attribute_heatmap` | PostgreSQL | 국가×속성 비율 매트릭스 |
| Order Server | `get_blue_ocean_combinations` | PostgreSQL | Phase 2 — 블루오션 탐색 |
| Order Server | `compare_seller_vs_market` | PostgreSQL | Phase 2 — 셀러 갭 분석 |

### 도구-서버 매핑 주입 (하드코딩 제거)

TraceLogger가 "이 도구가 어느 서버에 속하는지"를 알아야 하는데, 도구 목록을 하드코딩하면 도구 추가 시 TraceLogger를 수정해야 한다. 대신 오케스트레이터가 서버별 도구를 등록할 때 매핑을 자동 생성하여 TraceLogger에 주입한다. TraceLogger는 매핑만 받으면 되고, 도구 구성을 알 필요 없다(관심사 분리).

### ReAct while-loop: text block 캡처

LLM 응답에서 text block(사고 과정)과 tool_use block(도구 선택)을 분리 캡처한다. text block이 trace의 `reasoning` 필드가 되어, 프론트엔드에서 "왜 이 도구를 선택했는지" 의사결정 흐름도를 렌더링할 수 있다.

```
응답: [TextBlock("비율 추이를 확인하겠습니다"), ToolUseBlock("get_attribute_trend", {...})]
                  ↑ reasoning                      ↑ decision
```

<!-- 스크린샷: Zone C — Step 1의 Think(사고) / Act(도구 호출) / Observe(결과) 3단계가 보이는 상태 -->

### 결과 영속화: 같은 질문에 LLM 재호출 방지

오케스트레이터 결과(answer + steps + tool_output)를 `orchestrator_results` 테이블에 자동 저장한다. 동일 trace_id로 재조회하면 LLM 호출 없이 저장된 결과를 반환하여, Zone B 차트와 Zone C 트레이스가 완전히 복원된다.

---

## 대시보드: 기술 가시화

단일 페이지 3존 레이아웃. 질문 → 결과 + 의사결정 과정을 한 화면에서 본다.

```
┌──────────────────────────────────────────┬──────────────────────┐
│  Zone A — 질문 (접힘/펼침)                │                      │
├──────────────────────────────────────────┤  Zone C              │
│                                          │  Decision Trace      │
│  Zone B — 시각화 결과                     │                      │
│  도구별 자동 매핑:                        │  STEP 1 ● PostgreSQL │
│  get_attribute_trend → LineChart         │  Think → Act → Observe│
│  query_causal_chain → CausalFlow        │                      │
│  get_country_attribute_heatmap → Heatmap│  STEP 2 ● Neo4j      │
│  find_ingredient_synergies → SynergyList│  Think → Act → Observe│
│  최종 답변 → Markdown 렌더링             │                      │
├──────────────────────────────────────────┴──────────────────────┤
│  시스템 상태 바                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Zone C가 핵심 차별점.** LLM이 어떤 도구를 왜 선택했는지 실시간으로 보인다. 질문을 바꿀 때마다 다른 도구 조합이 보여서, 하드코딩이 아닌 LLM 자율 판단임을 증명한다.

<!-- 스크린샷: 같은 화면에서 질문만 바꿨을 때 Zone C의 도구 조합이 달라지는 모습 (2개 비교) -->

### Zone B — 도구별 시각화 자동 매핑

오케스트레이터 응답의 `steps`를 파싱하여 각 `tool_call`의 도구 이름에 따라 적절한 시각화를 자동 렌더링한다. 하드코딩된 화면이 아니라, LLM이 어떤 도구를 호출하든 그에 맞는 차트가 동적으로 구성된다.

| MCP 도구 | 시각화 | 데이터 소스 |
|----------|--------|-----------|
| `get_attribute_trend` | Recharts LineChart (국가별 월별 곡선) | PostgreSQL |
| `get_country_attribute_heatmap` | 색상 그리드 히트맵 (국가×속성) | PostgreSQL |
| `query_causal_chain` | 인과 플로우 (기후→피부고민→기능, strength 표시) | Neo4j |
| `find_trending_ingredients` | 수평 BarChart (성분별 상품 수) | Neo4j |
| `find_ingredient_synergies` | 뱃지 리스트 (도메인지식/동시출현 구분) | Neo4j |
| 최종 답변 | Markdown 렌더링 | Claude LLM |

<!-- 스크린샷: Zone B에 LineChart + CausalFlow + LLM Markdown이 동시에 보이는 상태 -->

---

## 핵심 파이프라인 3: PatternScout — 자율 패턴 탐지

### Phase 1의 한계: 시드 온톨로지는 정적이다

AnalystAgent는 Neo4j의 시드 인과 체인(기후→피부고민→기능)을 읽어서 "왜?"에 답한다. 하지만 시드 온톨로지는 도메인 전문가가 사전에 정의한 구조이므로, **데이터에서 새롭게 발생하는 패턴을 반영하지 못한다.** 예를 들어 "비건과 무기자차가 왜 함께 많이 나타나는가?"라는 질문에 AnalystAgent는 두 속성을 각각 따로 설명할 뿐, 동시 출현이 독립 기대치보다 높다는 **통계적 관계**는 시드에 없으므로 답할 수 없다.

이것은 시드 온톨로지 설계의 문제가 아니라 구조적 한계다. 시드는 "기후→피부고민→기능"이라는 **도메인 지식 기반의 인과 체인**을 담고 있고, 이 인과 체인은 데이터와 무관하게 참이다. 하지만 "비건 속성과 무기자차 속성이 독립 기대치보다 1.54배 많이 동시 출현한다"는 **데이터에서 관찰된 통계적 사실**이며, 이것은 시드에 사전 정의할 수 없다.

### PatternScout: 데이터에서 통계적 패턴을 찾아 온톨로지를 확장

PatternScout는 AnalystAgent와 **목적이 다른** 별도 에이전트다. AnalystAgent가 "사용자 질문에 답하기"라면, PatternScout는 "주문 데이터에서 통계적으로 유의미한 속성 간 패턴을 탐지"하는 것이 목적이다.

**핵심 사상**: 이 시스템이 찾는 것은 "인과"가 아니라 **"통계적 공존 패턴"**이다. 인과 검증은 프로덕션 A/B 테스트의 영역이고, PatternScout가 제안하는 것은 상관(correlation)이다. 시드 온톨로지의 기후→피부고민→수요는 도메인 지식에 기반한 인과이지만, PatternScout가 발견하는 것은 데이터에서 관찰된 통계적 관계다.

```
AnalystAgent (Phase 1):          PatternScout (Phase 2):
  트리거: 사용자 질문              트리거: 매 분석 턴 완료 후
  목표: 질문에 답하기              목표: 통계적 패턴 탐지
  도구: Data Tools (읽기만)        도구: Data + Logic + Action
  산출물: 인사이트 답변             산출물: 관계 제안 (사람 승인 필요)
```

### 구조화된 탐색 절차 — LLM은 "뭘 검사할지"만 판단

"자유롭게 가설을 세우세요"는 LLM이 뭘 해야 할지 몰라서 안전한 조회만 하고 끝난다. 실제로 테스트하면 LLM은 위험 회피적으로 행동하여 `get_attribute_trend` 같은 안전한 읽기 도구만 반복 호출하고, `propose_relationship` 같은 쓰기 도구는 호출하지 않는다. 대신 명시적 탐색 절차를 system prompt로 제공한다:

```
Step 1: 직전 분석의 주요 속성 파악 (예: "비건", JP, sunscreen)
Step 2: 같은 국가+카테고리의 상위 5개 속성 조회
Step 3: 주요 속성과 각 후보의 동시 출현 lift 계산
        → lift > 1.3 이고 sample_size > 30 이면 SYNERGY 제안
Step 4: 시계열 상관 계산
        → |correlation| > 0.6 이면 TEMPORAL_CORRELATION 제안
Step 5: 다른 국가와 비율 비교
        → p < 0.05 이면 CROSS_MARKET_GAP 제안
```

**LLM의 역할과 코드의 역할을 명확히 분리한 이유**: LLM이 "lift가 1.54입니다"라고 생성하면, 이 숫자는 어디서 왔는지 검증할 수 없다. LLM의 내부 가중치에서 나온 숫자이지, SQL 집계 결과가 아니다. 반면 `compute_cooccurrence_lift()`가 반환한 1.54는 `COUNT(*) FILTER WHERE ... / total`의 결과이므로 재현 가능하고, evidence에 SQL 결과를 그대로 저장하여 면접관이 검증할 수 있다.

**임계치 근거**: lift > 1.3은 역학 연구에서 "약한 연관(weak association)"의 하한으로 사용되는 값이다. 1.0 = 독립(동시 출현이 우연과 같음), 1.3 = 우연 대비 30% 이상 높은 동시 출현. sample_size > 30은 중심극한정리에 의해 표본 비율의 정규 근사가 성립하는 최소 표본 크기. |correlation| > 0.6은 사회과학에서 "강한 상관"의 하한.

### Palantir Stage→Review→Approve 패턴

```
LLM이 제안 → 통계 검증은 코드 → 승인은 사람

  PatternScout: "비건과 무기자차의 동시 출현 비율을 검사하겠습니다"
    → compute_cooccurrence_lift("비건", "무기자차", "JP", "sunscreen")
    → lift = 1.54 (코드가 계산)
    → propose_relationship("비건", "무기자차", "SYNERGY", {lift: 1.54})
    → relationship_proposals 테이블에 status='proposed' 저장
    → Neo4j에 PROPOSED_LINK 생성

  사람이 대시보드에서 [승인] 클릭
    → status → 'approved'
    → PROPOSED_LINK → DISCOVERED_LINK로 전환

  이후 AnalystAgent가 "비건+무기자차 왜?" 질문을 받으면
    → query_causal_chain("JP")에서 DISCOVERED_LINK도 반환
    → 답변: "비건과 무기자차는 시너지 관계(lift=1.54)입니다" ← Before와 다른 답변
```

### Before/After: 답변이 실제로 달라진다

```
Before (PatternScout 없음):
  질문: "비건과 무기자차를 함께 가진 상품이 많은 이유는?"
  답변: "비건은 클린뷰티 트렌드(58%), 무기자차는 UV차단 효과(47%)..."
  → 각각 따로 설명. 조합의 이유 없음.

After (PatternScout + 승인):
  같은 질문:
  답변: "비건과 무기자차는 시너지 관계. 동시 비율(42%)이 독립 기대치(27%)보다 1.54배 높음..."
  → 조합의 이유 + 통계적 수치 근거.
```

### 도구 확장: 8개 → 14개

| 서버 | 도구 | 역할 | Phase |
|------|------|------|-------|
| KG (Neo4j) | `query_causal_chain` | 시드 인과 + **DISCOVERED_LINK 통합 반환** | 1→2 확장 |
| KG | `find_trending_ingredients` | 성분별 상품 빈도 | 1 |
| KG | `get_product_graph` | 상품 그래프 컨텍스트 | 1 |
| KG | `find_ingredient_synergies` | 성분 시너지 | 1 |
| Order (PG) | `get_attribute_trend` | 월별 비율 시계열 | 1 |
| Order | `get_country_attribute_heatmap` | 국가×속성 매트릭스 | 1 |
| **Logic** | `compute_cooccurrence_lift` | 동시 출현 lift 계산 (코드) | **2 신규** |
| **Logic** | `compute_temporal_correlation` | 시계열 상관계수 (코드) | **2 신규** |
| **Logic** | `test_hypothesis` | 범용 가설 검증 (코드) | **2 신규** |
| **Action** | `propose_relationship` | 관계 제안 (PG + Neo4j) | **2 신규** |
| **Action** | `save_market_insight` | 인사이트 저장 | **2 신규** |
| Order | `get_blue_ocean_combinations` | 블루오션 (Phase 3 스텁) | 스텁 |
| Order | `compare_seller_vs_market` | 셀러 갭 (Phase 3 스텁) | 스텁 |

### 설계 결정: 통계 검증은 LLM이 아닌 코드가 수행

lift, correlation, p-value를 LLM이 생성하면 **통계적 근거 없는 숫자**가 된다. 코드가 SQL 집계로 계산하고, LLM은 "어떤 속성 쌍을 검사할지"만 판단한다. 계산 결과의 수치는 evidence로 DB에 저장되어 면접관이 검증할 수 있다.

이 분리가 가능한 이유: 도구 호출 패턴에서 LLM은 `compute_cooccurrence_lift(attr_a="비건", attr_b="무기자차", ...)` 형태로 **파라미터만 선택**하고, lift 계산 자체는 `COUNT(*) FILTER WHERE ... / total`의 SQL 집계다. LLM이 하는 일은 "비건-무기자차 쌍이 의미 있을 것 같다"는 가설 선택이지, 숫자 생성이 아니다.

### 설계 결정: query_causal_chain을 DISCOVERED_LINK 포함으로 확장

기존 Cypher는 시드 경로(`HAS_CLIMATE→TRIGGERS→DRIVES_DEMAND`)만 탐색하므로, 승인된 관계(`DISCOVERED_LINK`)를 안 읽으면 답변이 달라지지 않는다. 시드 인과 체인과 발견된 관계를 **통합 반환**하도록 확장하여, PatternScout 발견 → 승인 → AnalystAgent 답변 실제 개선이 연결된다.

반환 구조 변경: `list[dict]` → `{"seed_chains": [...], "discovered_links": [...]}`
- `seed_chains`: 기존과 동일한 인과 체인 리스트
- `discovered_links`: 승인된 DISCOVERED_LINK 관계 (type, evidence 포함)

이 변경의 영향을 받는 곳: LLM 오케스트레이터의 `_summarize_output()`, 프론트엔드 CausalChainView, Eval의 `_has_discovered_links()` — 전부 dict 구조를 처리하도록 수정. 기존 orchestrator_results에 저장된 Before 데이터는 list 형식이므로, `_has_discovered_links()`가 list/dict 양쪽을 처리하도록 구현하여 하위 호환 유지.

### 설계 결정: PatternScout를 AnalystAgent에서 분리

검토한 대안: 하나의 에이전트에 "질문 답변 + 패턴 탐지"를 모두 맡기기. 기각한 이유:

1. **system prompt 충돌**: "사용자 질문에 답하세요"와 "통계적 패턴을 탐지하세요"는 상충. 하나의 프롬프트에 넣으면 LLM이 질문 답변 중에 갑자기 `propose_relationship`을 호출하거나, 탐지 중에 사용자에게 답변을 시도.
2. **도구 집합 차이**: AnalystAgent는 읽기 도구만, PatternScout는 쓰기 도구(propose_relationship)도 사용. 읽기 전용 에이전트에 쓰기 권한을 주면 사용자 질문 중 의도치 않은 관계 제안이 발생할 수 있음.
3. **비용 제어**: PatternScout의 MAX_STEPS=7은 AnalystAgent(MAX_STEPS=5)보다 길다. 합치면 MAX_STEPS를 12로 올려야 하고, 한 번의 질문에 $0.10+ 비용이 발생.
4. **Eval 분리**: agent_type="analyst"와 agent_type="pattern_scout"로 trace를 구분해야 축 2(답변 품질)와 축 1(패턴 탐지)을 독립적으로 측정 가능.

### 이 접근의 한계: 솔직한 평가

**1. 시뮬레이션 데이터의 순환 논증 위험** — 데이터를 의도적 패턴으로 생성했고, PatternScout가 그 패턴을 "발견"한다. 이는 "숨겨놓은 보물을 찾는 게임"에 가깝고, 실 데이터에서의 발견 능력을 증명하지는 못한다. 이 한계를 인지하고, PatternScout의 가치는 "발견 능력" 자체보다 **발견→제안→검증→승인→답변 반영의 파이프라인 설계**에 있다.

**2. lift 임계치의 도메인 비의존성** — 1.3이라는 임계치가 뷰티 이커머스에서 최적인지는 검증되지 않았다. 실 운영에서는 도메인 전문가와 함께 임계치를 튜닝해야 한다. MVP에서는 "임계치가 조정 가능한 구조"임을 보여주는 것이 목적.

**3. 매 턴 실행의 비용 비효율** — MVP에서 PatternScout는 매 AnalystAgent 턴 후 자동 실행된다. 같은 국가+카테고리에 대해 반복 탐색하면 이미 발견한 패턴을 다시 검사하게 된다. 프로덕션에서는 일 배치/이벤트 트리거로 전환해야 한다. MVP에서 매 턴 실행하는 이유는 데모 시 즉시 결과를 보여주기 위함.

---

## Eval 프레임워크: Knowledge Growth 측정

### "답변이 풍부해지고 있다"를 데이터로 보여준다

4축 Eval로 시스템의 성장을 측정한다. PatternScout가 없을 때(Before)와 있을 때(After)의 스냅샷을 비교하여 개선을 정량화.

```
축 1: 패턴 탐지 현황      — PatternScout가 패턴을 찾고 있는가?
축 2: 답변 품질 개선률     — 승인된 관계가 답변을 실제로 바꾸는가? ⭐핵심
축 3: 추론 커버리지        — 데이터 근거로 답할 수 있는 범위가 넓어지는가?
축 4: 시스템 효율          — 전체 파이프라인이 작동하는가?
```

### 핵심 지표: discovered_usage_rate

```
Before (PatternScout 없음):
  analyses=3, discovered_usage=0 → rate=0%

After (PatternScout + 승인):
  analyses=5, discovered_usage=2 → rate=40%
  → "승인 후 답변의 40%가 발견된 관계를 활용"
```

이 수치가 0%에서 40%+로 점프하는 것이 **시스템이 성장하고 있다**는 핵심 증거.

### Before/After 답변 비교 — 숫자보다 강한 증거

discovered_usage_rate 40%라는 숫자보다, **두 답변을 나란히 읽는 것**이 면접관에게 100배 설득력 있다. 같은 질문의 승인 전/후 답변을 자동으로 찾아서 대시보드에서 비교할 수 있다.

### 설계 결정: Eval 상수 하드코딩 제거

국가·유형 목록을 코드에 하드코딩하지 않고 Neo4j Country/ProductType 노드에서 동적 조회. 시드 변경 시 eval 코드 수정 불필요 (ADR-015).

### 설계 결정: 기각한 Eval 지표들

| 기각한 지표 | 기각 이유 |
|-----------|----------|
| Evidence density (답변 내 수치 개수) | 숫자가 많다고 답변이 좋은 건 아님. proxy로 너무 약함 |
| LLM-as-judge (Claude가 두 답변을 비교) | LLM이 LLM을 평가하는 순환. 면접관이 직접 읽는 게 더 신뢰 |
| Trace step 수 비교 | Before/After 모두 3 steps로 차이 없음. 의미 없음 |
| 답변 길이 비교 | 길다고 좋은 게 아님 |
| 속성 추출 F1 | 우리 가정(한국어, 4브랜드, 5카테고리)에서 난이도 낮아 포폴 임팩트 부족 |

---

## 엔지니어링 결정 기록 (ADR)

아키텍처 결정을 [`docs/adr/`](docs/adr/)에 기록했다. 각 결정은 맥락, 검토한 대안, 선택 근거, 결과를 포함한다.

| ADR | 결정 | 핵심 근거 |
|-----|------|----------|
| 001 | Neo4j 온톨로지 | SQL 집계로는 인과 체인 도출 불가 |
| 002 | Golden Example few-shot | 스키마 일관성 + flywheel 확장성 |
| 003 | 자동 속성 승격 루프 | 사람 손 최소화, 트렌드 자동 반영 |
| 004 | MCP Server 데이터 노출 | LLM 자율 도구 선택 + 추적성 |
| 005 | Tool Use + Few-Shot 2레이어 | 구조 강제 + 값 형식 유도 분리 |
| 006 | Confidence 모듈 제거 | MVP에서 운영 시나리오 없음 |
| 007 | SOLD_IN 단순화 | Neo4j=왜, PostgreSQL=얼마나 역할 분리 |
| 008 | Python 3.12 고정 | sentence-transformers/torch 호환성 |
| 009 | 도구-서버 매핑 주입 | 하드코딩 제거, 관심사 분리 |
| 010 | Pydantic 도구 스키마 자동 생성 | 수동 300줄 → BaseModel 5줄, 단일 진실 소스 |
| 011 | 원본 키워드 보존 | 추출 시 동의어 변환 금지, 정보 손실 방지 |
| 012 | 오케스트레이터 결과 영속화 | LLM 재호출 방지, 이력 재조회 |
| 013 | Zone B 시각화 자동 매핑 | 도구→차트 동적 결정, 하드코딩 화면 아님 |
| 014 | Zone C ReAct UI (Think/Act/Observe) | LLM 사고 과정 가시화 |
| 015 | Eval 상수 하드코딩 제거 | Neo4j에서 동적 조회, 단일 진실 소스 |
| 016 | PatternScout 에이전트 분리 | 목적·권한·비용·Eval 분리 필요 |
| 017 | 통계 검증은 코드가 수행 | LLM 생성 숫자는 재현·검증 불가 |
| 018 | 구조화된 탐색 절차 | 자유 탐색은 LLM이 안전 도구만 반복 |
| 019 | query_causal_chain DISCOVERED_LINK 확장 | 승인된 관계가 답변에 실제 반영되려면 필수 |

---

## 한계점과 향후 계획

### 현재 한계

**1. 시뮬레이션 데이터의 순환 논증** — 데이터를 의도적 패턴(A~J)으로 생성했고, PatternScout가 그 패턴을 "발견"한다. 이는 "숨겨놓은 보물을 찾는 게임"에 가깝고, 실 데이터에서의 발견 능력을 증명하지는 못한다. PatternScout의 가치는 발견 능력 자체보다 **발견→제안→검증→승인→답변 반영의 파이프라인 설계**에 있다. MCP 서버 구조이므로 시뮬레이션 서버를 실 API 서버로 교체하면 나머지 코드 변경 없이 동작.

**2. 통계적 상관 ≠ 인과** — PatternScout가 찾는 것은 "비건과 무기자차가 기대치보다 높은 빈도로 동시 출현한다"는 통계적 사실이지, "비건이 무기자차를 유발한다"는 인과가 아니다. 인과 검증은 프로덕션 A/B 테스트의 영역. 시드 온톨로지의 기후→피부고민→수요는 도메인 전문가가 정의한 인과이고, PatternScout의 발견은 상관이다. 이 구분을 시스템이 명시적으로 표현한다 (seed_chains vs discovered_links).

**3. 임계치의 도메인 비의존성** — lift > 1.3, |correlation| > 0.6 등의 임계치가 뷰티 이커머스에서 최적인지는 검증되지 않았다. 통계학 일반 관례에서 차용한 값이며, 실 운영에서는 도메인 전문가와 함께 튜닝해야 한다.

**4. 스트리밍 미지원** — 오케스트레이터가 전체 완료 후 응답. Step별 SSE 스트리밍을 구현하면 Zone C가 실시간으로 업데이트되는 UX가 가능하지만 현재 미구현.

**5. 매 턴 PatternScout 실행의 비효율** — MVP에서 매 AnalystAgent 턴 후 자동 실행. 같은 국가+카테고리에 대해 반복 탐색하면 이미 발견한 패턴을 다시 검사. 프로덕션에서는 일 배치/이벤트 트리거로 전환해야 한다.

### 향후 계획

- **5-dimension Trajectory Eval** — TRAJECT-Bench(ICLR 2026) 참고. 도구 선택·파라미터·순서·출력 활용·사고-행동 일치를 평가
- **Ontology-Grounded Eval** — Neo4j 온톨로지를 검증 기준으로 활용. LLM 답변의 주장이 온톨로지에 근거 있는지 자동 검증
- **스트리밍** — SSE 기반 step별 실시간 응답
- **시맨틱 캐시** — 임베딩 유사도 기반 질문 중복 감지 → 캐시 히트 시 LLM 재호출 방지
- **배치 트리거** — PatternScout를 매 턴이 아닌 일 배치/데이터 변경 이벤트로 전환

---

## 기술 스택

| 영역 | 기술 | 선택 이유 |
|------|------|----------|
| Runtime | Python 3.12 | sentence-transformers/torch 호환 (3.14 미지원) |
| Web | FastAPI | async-first, Pydantic 통합 |
| Graph DB | Neo4j 5.26 | 인과 체인 네이티브 표현, Cypher |
| RDB | PostgreSQL 16 | JSONB 집계, 시계열 GROUP BY |
| Vector DB | ChromaDB 1.5 (PersistentClient) | 로컬 임베딩, 컨테이너 불필요 |
| Embedding | intfloat/multilingual-e5-large | 1024차원, 한/일/영 다국어 |
| LLM | Claude Sonnet 4 (Anthropic) | Tool Use 강제, ReAct 패턴 |
| ORM | SQLAlchemy (async) | 비동기 DB 접근 |
| Frontend | Next.js 16 + React 19 + shadcn/ui | App Router, Tailwind |
| Chart | Recharts | LineChart, BarChart, 커스텀 히트맵 |
| Test | pytest + pytest-asyncio | 57건 단위 + 4건 통합 (실제 Claude API) |

**의도적으로 사용하지 않은 것**: LangChain, LangGraph — Tool Use를 직접 구현하여 파이프라인을 완전히 제어하고, tool_call_traces 로깅을 자유롭게 커스터마이징.

---

## 데이터 현황

| 항목 | 수량 |
|------|------|
| Gold Examples | 50건 (5유형 × 10건) |
| 주문 데이터 | 1,000건 (Cafe24 495 + Qoo10 342 + Shopee 163) |
| Neo4j 온톨로지 | 39노드, 34관계 (시드) |
| Neo4j Product | 1,000노드 (graph_sync) |
| Neo4j 관계 합계 | MADE_BY 1,000 + CONTAINS 724 + IS_TYPE/SOLD_IN/SOLD_ON 각 1,000 |
| Extractions | 1,000건 |
| 단위 테스트 | 57건 |
| 통합 테스트 | 4건 (실제 Claude API, $0.135) |
| ADR | 14건 |
| API 엔드포인트 | 11개 |

### 주문 데이터 패턴 (검증용)

| 패턴 | 설명 | 검증 결과 |
|------|------|----------|
| A | JP 선크림 "비건" 19%→56% 상승 | ✅ 확인 |
| B | SG 선크림 "워터프루프" 71~80% 안정 | ✅ 확인 |
| C | JP 선크림 "톤업" 67%→44% 하락 | ✅ 확인 |
| D | JP "비건+무기자차" 블루오션 (1상품, 고반복) | Phase 2 |
| E | "마이크로바이옴" 신규 속성 등장 (0→25건) | Phase 2 |
| F | 국가별 성분 선호도 차이 (JP=히알루론산, SG=나이아신아마이드) | Phase 2 |

---

## 실행 방법

```bash
# 인프라
docker compose up -d postgres neo4j

# 백엔드
cd backend
/usr/local/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m data.seed_neo4j
python -m data.seed_db
python -m data.build_index
python -m data.bootstrap_extract --clean
uvicorn main:create_app --factory --port 8000

# 프론트엔드
cd frontend
npm install && npm run dev    # http://localhost:3000

# 테스트
cd backend
pytest tests/unit/ -v         # 57건 단위 테스트
```
