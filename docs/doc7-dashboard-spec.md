# [Doc 7 v2] 대시보드 UX — 단일 화면 인텔리전스 대시보드

> 원본 Doc 7에 구현 과정의 피드백을 반영한 최종 버전.
> 직접 구현한 11개 ADR, 50건 단위테스트, 4건 실제 API 통합테스트,
> 8개 MCP 도구, ReAct 오케스트레이터, Pydantic 도구 데코레이터 등의
> 기술적 결정이 화면에서 어떻게 보여야 하는지를 설계한다.

---

## 0. 설계 원칙 — 면접관이 3분 안에 이해해야 하는 것

```
면접관이 봐야 하는 것 (우선순위):

1. "LLM이 질문에 따라 다른 도구를 자동으로 선택한다"
   → Zone C에서 질문마다 다른 도구 조합이 보여야 함

2. "Neo4j(왜) + PostgreSQL(얼마나) + LLM(그래서)의 3-소스 조합"
   → Zone C에서 각 step의 MCP 서버(kg/order)가 구분되어 보여야 함

3. "속성 추출이 스키마 일관성을 강제한다"
   → 추출 모드에서 Tool Use + Few-Shot 파이프라인 과정이 보여야 함

4. "의사결정 과정이 투명하게 추적 가능하다"
   → Zone C의 reasoning(사고) + decision(도구) + result(결과) 흐름

면접관이 안 봐도 되는 것:
- 복잡한 차트 인터랙션, 드래그앤드롭
- 반응형 모바일 레이아웃
- 로딩 스피너의 정교한 애니메이션
```

---

## 1. 3존 레이아웃 (원본 유지 + 보강)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  MarketPulse — K-Beauty Cross-Border Intelligence Engine                │
├─────────────┬──────────────────────────────┬────────────────────────────┤
│  ZONE A     │  ZONE B                      │  ZONE C                    │
│  질문 패널   │  인텔리전스 결과              │  의사결정 트레이스           │
│  (280px)    │  (flex-1)                    │  (400px) ← 360→400 확대    │
│             │                              │                            │
│  모드 선택   │  도구별 자동 시각화           │  Step 흐름도               │
│  프리셋 질문 │  히트맵/차트/인과/해석        │  reasoning → tool → result  │
│  직접 입력   │                              │  비용/레이턴시 투명         │
├─────────────┴──────────────────────────────┴────────────────────────────┤
│  시스템 상태 바 — 추출 건수, 비용, Neo4j 노드, 스키마 준수율              │
└──────────────────────────────────────────────────────────────────────────┘
```

### 원본 대비 변경

- **Zone C 폭 360→400px**: reasoning 텍스트가 잘리지 않게. 이 패널이 핵심 차별점이므로 넉넉하게.
- **Zone B에 "아키텍처 개요" 초기 화면 추가**: 질문 전 빈 화면이 아니라, 시스템 아키텍처 다이어그램을 보여줌.

---

## 2. Zone A — 질문 패널 (보강)

### 2.1 프리셋 질문 — ANSWER_SHEET S-01~S-15 매핑

```
┌───────────────────────────┐
│ 모드: [인텔리전스] [추출]  │
│                           │
│ ── 트렌드 분석 ──          │
│ ● JP 비건 선크림 상승 (S-01)   → 패턴 A
│ ● JP 톤업 선크림 하락 (S-02)   → 패턴 C
│ ● SG 워터프루프 일관 (S-03)    → 패턴 B
│                           │
│ ── 인과 추론 ──            │
│ ● JP 비건+무기자차 왜? (S-05)  → 패턴 D + Neo4j
│ ● JP 선크림 왜 잘 팔려? (S-10) → 복합
│                           │
│ ── 시장 분석 ──            │
│ ● JP 블루오션 기회 (S-04)      → 패턴 D
│ ● 국가별 성분 선호 (S-08)      → 패턴 F
│ ● SG 진출 전략 (S-09)         → 패턴 F+B
│                           │
│ ── 신규 속성 ──            │
│ ● 마이크로바이옴 감지 (S-06)   → 패턴 E
│                           │
│ ── 함정 질의 ──            │
│ ● SG 워터프루프 트렌드? (S-12) → 엣지케이스
│ ● KR 비건 트렌드? (S-13)      → 엣지케이스
│                           │
│ ─────────────────         │
│ 직접 질문:                 │
│ ┌───────────────────────┐ │
│ │ ...                    │ │
│ └───────────────────────┘ │
│ [ 분석하기 ]              │
└───────────────────────────┘
```

### 추가 — 프리셋에 기대 동작 힌트

각 프리셋 옆에 **어떤 도구가 호출될지 미리 표시**하면 면접관이 "이 질문은 Neo4j를 쓸 것이고, 저 질문은 PostgreSQL을 쓸 것"이라는 기대를 갖고 Zone C를 볼 수 있다.

```
● JP 비건 선크림 상승     [order]
● JP 비건+무기자차 왜?    [kg] [order]
● 전체 시장 현황          [kg] [order] ×2+
```

### 2.2 추출 모드 — 프리셋 상품명

ANSWER_SHEET S-14, S-15 기반:
```
● 이니스프리 아쿠아 UV 프로텍션 크림 SPF50+ PA++++ 50ml 비건 무기자차
● 토리든 다이브인 워터리 선크림 SPF50+ PA++++ 60ml 워터프루프
● 라운드랩 독도 토너 300ml 약산성 히알루론산
● [1+1] 코스알엑스 AHA/BHA 토너 150ml
● 직접 입력: [                                ]
```

---

## 3. Zone B — 인텔리전스 결과 (보강)

### 3.1 초기 화면 — 시스템 아키텍처 개요

질문 전 빈 화면 대신, 시스템 아키텍처를 보여준다.
면접관이 처음 화면을 열었을 때 "이 시스템이 뭔지" 즉시 파악 가능.

```
┌──────────────────────────────────────────────────┐
│                                                  │
│  MarketPulse Architecture                        │
│                                                  │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐     │
│  │ Neo4j   │    │PostgreSQL│    │ChromaDB │     │
│  │ "왜?"   │    │ "얼마나?"│    │"비슷한?" │     │
│  │ 인과체인 │    │ 집계     │    │ few-shot │     │
│  └────┬────┘    └────┬─────┘    └────┬────┘     │
│       │              │               │          │
│       └──────┬───────┘               │          │
│              ▼                       │          │
│  ┌───────────────────┐               │          │
│  │ LLM Orchestrator  │◄──────────────┘          │
│  │ (ReAct + 8 Tools) │                          │
│  └───────────────────┘                          │
│                                                  │
│  왼쪽에서 질문을 선택하면                          │
│  LLM이 도구를 자동 선택하여 분석합니다.             │
│                                                  │
│  Gold: 50건 | Orders: 1,000건 | Neo4j: 1,039노드  │
│  ADR: 11건 | Tests: 54건 | API: 11개              │
└──────────────────────────────────────────────────┘
```

### 3.2 도구 결과 → 시각화 매핑 (원본 유지)

```typescript
function determineVisualizations(response: OrchestratorResponse) {
  const visuals = [];
  for (const step of response.steps) {
    if (step.type !== "tool_call") continue;
    switch (step.tool) {
      case "get_country_attribute_heatmap":
        visuals.push({ type: "heatmap", data: step.tool_output });
        break;
      case "get_attribute_trend":
        visuals.push({ type: "trend_chart", data: step.tool_output });
        break;
      case "query_causal_chain":
        visuals.push({ type: "causal_chain", data: step.tool_output });
        break;
      case "find_ingredient_synergies":
        visuals.push({ type: "synergy_list", data: step.tool_output });
        break;
      case "find_trending_ingredients":
        visuals.push({ type: "ingredient_bar", data: step.tool_output });
        break;
    }
  }
  visuals.push({ type: "llm_insight", data: response.answer });
  return visuals;
}
```

### 3.3 시각화 상세

**히트맵 (HeatmapView)**:
- X축: 속성 (비건, 톤업, 워터프루프, ...)
- Y축: 국가 (KR, JP, SG)
- 색상: 비율 (0%=흰색 → 80%+=진한 파랑)
- 셀 호버: 정확한 수치 + 건수

**시계열 차트 (TrendChartView)**:
- Recharts LineChart
- 국가별 라인 색상 구분
- 6개월 X축
- 상승/하락 트렌드 화살표 표시

**인과 체인 (CausalChainView)**:
- 수평 플로우: `기후 → 피부고민 → 기능`
- 각 화살표에 strength 값
- 가장 강한 체인 하이라이트

**성분 시너지 (SynergyListView)**:
- explicit_synergy: 도메인 지식 뱃지
- co_occurrence: 데이터 기반 뱃지 + 상품 수

**LLM 인사이트 (LLMInsightText)**:
- 마크다운 렌더링
- "AI 분석" 라벨
- 하단에 trace_id 링크

### 3.4 추출 모드 결과 (원본 유지 + 보강)

```
┌─────────────────────┬───────────────────────────┐
│ 속성 카드            │ 메타 정보                  │
│                     │                           │
│ 제품유형: 선크림     │ Few-Shot 매칭:             │
│ 브랜드: 이니스프리   │  gold_007 (sim: 0.97)     │
│ SPF: 50+            │  gold_011 (sim: 0.91)     │
│ PA: ++++            │  gold_005 (sim: 0.94)     │
│ 용량: 50ml          │                           │
│ 기능: [UV차단]       │ 검증: ✅ errors 0         │
│ 가치: [비건]         │       ⚠️ warnings 1       │
│ 추가속성:           │                           │
│  자차타입: 무기자차   │ graph_sync: ✅             │
│                     │ 비용: $0.004 | 1,203ms    │
└─────────────────────┴───────────────────────────┘
```

---

## 4. Zone C — 의사결정 트레이스 (핵심 보강)

### 4.1 Step 카드 구조 — reasoning 강조

원본에서 reasoning이 안 보이면 "그냥 도구를 호출했구나"로 보일 위험.
**LLM의 사고 과정을 반드시 눈에 띄게** 보여야 한다.

```
┌────────────────────────────────────┐
│ Step 1                             │
│                                    │
│ 💭 "비율 추이를 먼저 확인하여      │  ← reasoning (연한 배경)
│    '상승 중'이 사실인지             │
│    검증하겠습니다."                 │
│                                    │
│ ─── 도구 호출 ───                  │
│ 🔧 get_attribute_trend             │
│ 📦 MCP: order (PostgreSQL)         │  ← 어떤 DB를 쓰는지 명시
│                                    │
│ Input:                             │
│ ┌────────────────────────────────┐ │
│ │ attribute_name: "비건"          │ │  ← font-mono, JSON 구조
│ │ attribute_type: "value"         │ │
│ │ countries: ["JP"]               │ │
│ └────────────────────────────────┘ │
│                                    │
│ Output: JP: 19.0% → 56.0%         │  ← summary (핵심 수치만)
│ [▶ 전체 응답 보기]                  │  ← 펼치면 full JSON
│                                    │
│ ✅ 1,203ms | $0.003                │
└────────────────────────────────────┘
        │
        ▼ (화살표 연결선)
┌────────────────────────────────────┐
│ Step 2                             │
│                                    │
│ 💭 "18%→56% 상승이 확인됐습니다.   │
│    이제 인과 체인으로 '왜'를        │
│    설명하겠습니다."                 │
│                                    │
│ ─── 도구 호출 ───                  │
│ 🔧 query_causal_chain              │
│ 📦 MCP: kg (Neo4j)                 │
│                                    │
│ Input: {country_code: "JP"}        │
│ Output: UV손상(0.88)→UV차단(0.92)  │
│ [▶ 전체 응답 보기]                  │
│                                    │
│ ✅ 89ms | $0.001                   │
└────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────┐
│ Step 3 — 최종 답변                  │
│                                    │
│ 💭 "수치와 인과 근거를 종합하여     │
│    셀러에게 인사이트를 생성합니다." │
│                                    │
│ 📝 LLM 텍스트 생성                  │
│ tokens: 2.8K in / 1.2K out        │
│ $0.008                             │
└────────────────────────────────────┘

━━━ 요약 ━━━━━━━━━━━━━━━━━━━━━━━━
steps: 3 | 도구: 2회
  📦 order: 1회 (PostgreSQL)
  📦 kg: 1회 (Neo4j)
총 비용: $0.012 | 총 시간: 3.4s
```

### 4.2 핵심 보강 — MCP 서버 시각적 구분

각 step에서 어떤 DB를 썼는지가 **색상 코드**로 구분되어야 한다.
면접관이 "아 이건 Neo4j를 쓴 거구나, 저건 PostgreSQL이구나" 즉시 파악.

```
order (PostgreSQL): 좌측 보더 파란색
kg (Neo4j):         좌측 보더 녹색
final_answer:       좌측 보더 회색
```

### 4.3 추출 모드 트레이스 (원본 유지 + 보강)

```
Step 1: 벡터 검색 (ChromaDB)       ← 보라색 보더
  gold_007(0.97) gold_011(0.91) gold_005(0.94)
  combined score: sim×0.7 + richness×0.3
        │
        ▼
Step 2: LLM 추출 (Claude Sonnet 4) ← 주황색 보더
  Tool Use forced + Few-Shot 3건 주입
  $0.004 | 1,050ms
        │
        ▼
Step 3: 규칙 기반 검증              ← 회색 보더
  errors: 0 ✅ | warnings: 1 ⚠️
  "환각 의심: 성분 '나이아신아마이드' 원본에 없음"
        │
        ▼
Step 4: graph_sync (Neo4j)         ← 녹색 보더
  Product ✅ | MADE_BY ✅
  IS_TYPE ✅ | SOLD_IN ✅
  CONTAINS: 히알루론산 ✅, 징크옥사이드 ✅
```

---

## 5. 하단 바 — 시스템 상태 (보강)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 📊 추출: 1,000건 | 💰 비용: $4.20 | 🔵 Neo4j: 1,039노드 4,758관계 |   │
│ 🧪 테스트: 54건 | 📋 ADR: 11건 | 🔌 API: 11 endpoints | 🐍 Python 3.12│
└──────────────────────────────────────────────────────────────────────────┘
```

각 지표 클릭 시 상세 팝오버:
- 추출 → error율, graph_sync 비율
- Neo4j → 노드/관계 타입별 분포
- 테스트 → 단위 50 + 통합 4 = 54건

---

## 6. 데이터 흐름 — API 호출 상세

### 인텔리전스 모드

```
프리셋 클릭 → POST /api/v1/orchestrator/ask {query: "..."}

응답 구조 (OrchestratorResult):
{
  answer: "일본 선크림 시장에서 비건이...",
  trace_id: "abc-123",
  steps: [
    {step: 1, type: "tool_call", reasoning: "비율 추이부터...",
     tool: "get_attribute_trend", tool_input: {...},
     tool_output_summary: "JP: 19%→56%", mcp_server: "order",
     latency_ms: 1203},
    {step: 2, type: "tool_call", reasoning: "상승 확인, 인과...",
     tool: "query_causal_chain", ...},
    {step: 3, type: "final_answer", reasoning: "종합...",
     answer: "..."}
  ],
  total_steps: 3,
  total_cost_usd: 0.012
}

Zone B: steps에서 tool_call을 파싱 → 도구별 시각화 자동 매핑
Zone C: steps를 순서대로 렌더링 (reasoning + tool + result)
```

### 추출 모드

```
상품명 입력 → POST /api/v1/extract {product_name: "..."}

응답 구조 (ExtractResponse):
{
  attributes: {productType: "선크림", brand: "이니스프리", ...},
  validation_passed: true,
  errors: [],
  warnings: ["환각 의심: ..."],
  examples_used: ["gold_007", "gold_011", "gold_005"],
  avg_similarity: 0.94,
  cost_usd: 0.004,
  latency_ms: 1203,
  graph_synced: true
}

Zone B: attributes → 속성 카드 + 메타 카드
Zone C: 파이프라인 과정 (벡터검색 → LLM → 검증 → graph_sync)
```

### 시스템 상태

```
GET /api/v1/extract/stats

응답:
{
  total_extractions: 1000,
  total_cost_usd: 4.20,
  graph_synced_count: 1000,
  graph_synced_ratio: 1.0,
  error_count: 0,
  error_ratio: 0.0,
  avg_latency_ms: 45.2
}
```

---

## 7. 기술 스택

```
Next.js 15 (App Router)     단일 페이지 — app/page.tsx
React 19                    클라이언트 인터랙션
shadcn/ui                   Card, Badge, Tabs, ScrollArea, Collapsible, Separator
Recharts                    히트맵(커스텀), LineChart, BarChart
TanStack Query v5           서버 상태 + 캐싱 + 로딩 상태 관리
Tailwind CSS 4              3-column flex 레이아웃
```

---

## 8. 컴포넌트 트리

```
app/page.tsx — DashboardPage
├── TopBar
│   └── "MarketPulse — K-Beauty Cross-Border Intelligence Engine"
│
├── MainLayout (flex, h-[calc(100vh-120px)])
│   │
│   ├── ZoneA — QueryPanel (w-[280px], border-r, overflow-y-auto)
│   │   ├── ModeSelector (Tabs: 인텔리전스 / 추출)
│   │   ├── [인텔리전스]
│   │   │   ├── PresetQuestionList (카테고리별 그룹)
│   │   │   │   └── PresetItem (질문 + 도구 힌트 뱃지)
│   │   │   └── CustomQueryInput (textarea + 분석하기 버튼)
│   │   └── [추출]
│   │       ├── PresetProductList (예시 상품명)
│   │       └── CustomProductInput
│   │
│   ├── ZoneB — ResultPanel (flex-1, overflow-y-auto, p-6)
│   │   ├── [초기] ArchitectureOverview (시스템 다이어그램)
│   │   ├── [인텔리전스] VisualizationStack
│   │   │   ├── HeatmapView (조건부)
│   │   │   ├── TrendChartView (조건부)
│   │   │   ├── CausalChainView (조건부)
│   │   │   ├── IngredientBarView (조건부)
│   │   │   ├── SynergyListView (조건부)
│   │   │   └── LLMInsightCard (항상)
│   │   └── [추출] ExtractionResultView
│   │       ├── AttributeCard
│   │       └── MetaCard (few-shot, validation, graph_sync, cost)
│   │
│   └── ZoneC — TracePanel (w-[400px], border-l, overflow-y-auto)
│       ├── TraceHeader (trace_id, 질문 요약)
│       ├── [인텔리전스] StepFlowList
│       │   ├── StepCard × N (reasoning + tool + input/output + cost)
│       │   ├── StepConnector (화살표)
│       │   └── FinalAnswerCard
│       ├── [추출] ExtractionTraceFlow
│       │   ├── VectorSearchStep
│       │   ├── LLMExtractionStep
│       │   ├── ValidationStep
│       │   └── GraphSyncStep
│       └── TraceSummary (steps, 도구별 분포, 총 비용, 총 시간)
│
└── BottomBar — SystemStatusBar
    ├── ExtractionStat (건수, 비용)
    ├── Neo4jStat (노드, 관계)
    ├── TestStat (54건)
    └── TechStat (ADR 11건, API 11개)
```

---

## 9. 면접 데모 시나리오 (3분)

```
[0:00] 화면 열기 — Zone B에 아키텍처 개요 보임
       "3개 데이터 소스를 LLM이 자동 조합하는 시스템입니다"

[0:30] 프리셋 "JP 비건 선크림 상승" 클릭
       Zone C에 Step이 하나씩 추가됨
       "LLM이 먼저 PostgreSQL에서 수치를 확인하고..."
       Zone B에 시계열 차트 나타남 (19%→56%)

[1:00] 프리셋 "JP 비건+무기자차 왜?" 클릭
       Zone C에 다른 도구 조합 보임 (kg + order)
       "이번에는 Neo4j 인과 체인도 호출합니다"
       Zone B에 인과 체인 + LLM 해석

[1:30] 추출 모드로 전환 → 프리셋 상품명 클릭
       Zone C에 파이프라인 과정 (벡터검색→LLM→검증→graph_sync)
       "Few-Shot으로 스키마 일관성을 강제합니다"

[2:00] Zone C를 가리키며:
       "모든 도구 선택 과정이 DB에 기록됩니다.
        어떤 질문에 어떤 도구를 왜 선택했는지 추적 가능합니다."

[2:30] 하단 바 가리키며:
       "1,000건 추출, 54건 테스트, 11개 ADR.
        비용은 건당 $0.004입니다."

[3:00] 직접 입력으로 자유 질문
       "정해진 질문만 되는 게 아니라, 자연어로 아무 질문이나 가능합니다."
```

---

## 10. Sprint 체크리스트

```
□ 프로젝트 셋업
  ├ Next.js 15 + shadcn + Recharts + TanStack Query
  └ Tailwind 3-column 레이아웃

□ DashboardPage 레이아웃
  ├ 3존 flex + TopBar + BottomBar
  └ ModeSelector (인텔리전스/추출)

□ Zone A — QueryPanel
  ├ PresetQuestionList (ANSWER_SHEET S-01~S-13 매핑, 도구 힌트 뱃지)
  ├ CustomQueryInput
  └ 추출 모드 (PresetProductList + CustomProductInput)

□ Zone B — ResultPanel
  ├ ArchitectureOverview (초기 화면)
  ├ VisualizationStack + determineVisualizations()
  ├ HeatmapView (커스텀 그리드 + 색상 스케일)
  ├ TrendChartView (Recharts LineChart)
  ├ CausalChainView (수평 플로우)
  ├ IngredientBarView (Recharts BarChart)
  ├ SynergyListView (explicit/co_occurrence 뱃지)
  ├ LLMInsightCard (마크다운 렌더링)
  └ ExtractionResultView (AttributeCard + MetaCard)

□ Zone C — TracePanel ⭐
  ├ StepCard (reasoning 강조, MCP 서버 색상 코드, input/output 접기)
  ├ StepConnector (화살표)
  ├ FinalAnswerCard
  ├ ExtractionTraceFlow (벡터검색→LLM→검증→graph_sync)
  └ TraceSummary (도구별 분포 파이차트, 비용, 시간)

□ BottomBar (SystemStatusBar)
  └ GET /api/v1/extract/stats 연동 + Neo4j 통계

□ 통합 테스트
  ├ 프리셋 "JP 비건 상승" → Zone B 차트, Zone C 2-step (order→final)
  ├ 프리셋 "JP 비건+무기자차 왜?" → Zone C에 kg+order 조합
  ├ 추출 모드 → Zone B 속성카드, Zone C 4-step 파이프라인
  └ 질문별 Zone C 도구 조합이 다른지 확인

□ 면접 데모 리허설 (3분 시나리오)
```

---

## 11. 백엔드 API 엔드포인트 요약 (프론트엔드 연동용)

```
# 인텔리전스 오케스트레이터
POST /api/v1/orchestrator/ask          {query: string} → OrchestratorResult
GET  /api/v1/orchestrator/traces       최근 trace 목록
GET  /api/v1/orchestrator/trace/:id    특정 trace 상세

# 직접 조회 (히트맵 초기 로딩 등)
GET  /api/v1/intelligence/heatmap      ?type=&start=&end=
GET  /api/v1/intelligence/trend        ?attribute=&type=&countries=

# KG 직접 조회
GET  /api/v1/kg/causal-chain/:country
GET  /api/v1/kg/trending/:country
GET  /api/v1/kg/product/:id

# 속성 추출
POST /api/v1/extract                   {product_name: string} → ExtractResponse

# 시스템 상태
GET  /api/v1/extract/stats             → ExtractStatsResponse
GET  /api/v1/health                    → {status, checks}
```
