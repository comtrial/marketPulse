# Eval 대시보드 프론트엔드 작업 지시서

## 목표

MarketPulse의 **Knowledge Growth 대시보드**를 구현한다. LLM 기반 시스템이 "시간이 지남에 따라 더 나은 답변을 하게 되는가?"를 4축으로 시각화한다.

---

## 1. 무엇을 보여주는가

### 상단 바 — Knowledge Growth 요약 (4축)

```
┌─ Knowledge Growth ───────────────────────────────────────────────┐
│  🔍 패턴 탐지         📈 답변 품질       🧠 추론 커버     ⚡ 효율 │
│  0건 제안/0건 승인    0% 관계 활용      80% 근거제시   데이터부족│
│  [▼ 상세 보기]                                                   │
└──────────────────────────────────────────────────────────────────┘
```

각 축의 의미:
- **패턴 탐지**: PatternScout가 몇 개의 관계를 제안/승인했는가 (현재 0 — Phase 2에서 채워짐)
- **답변 품질**: 승인된 관계(DISCOVERED_LINK)가 실제 답변에 활용되는 비율 (핵심 지표)
- **추론 커버리지**: 국가×유형 조합 중 LLM이 인과 근거를 가지고 답할 수 있는 비율
- **시스템 효율**: 세션 진행에 따른 비용 변화

### 상세 보기 (펼침)

4가지 시각화:
1. **답변 품질 추이 차트** — discovered_usage_rate의 세션별 변화 (LineChart)
2. **제안된 관계 테이블** — 관계 목록 + 승인/거부 버튼
3. **커버리지 매트릭스** — 국가×유형 그리드 (●● full / ●○ partial / ○○ none)
4. **Before/After 답변 비교** — 같은 질문의 승인 전/후 답변을 나란히 표시

---

## 2. 백엔드 API 스펙

### 기본 Eval API

| Endpoint | Method | 응답 | 용도 |
|----------|--------|------|------|
| `/api/v1/eval/full` | GET | 4축 통합 JSON | 상단 바 + 상세 보기 전체 데이터 |
| `/api/v1/eval/pattern-discovery` | GET | 축 1 상세 | 탐지 현황 |
| `/api/v1/eval/answer-quality` | GET | 축 2 상세 | 답변 품질 |
| `/api/v1/eval/reasoning-coverage` | GET | 축 3 상세 | 커버리지 매트릭스 |
| `/api/v1/eval/system-efficiency` | GET | 축 4 상세 | 비용 추이 |
| `/api/v1/eval/before-after-pairs` | GET | 비교 쌍 리스트 | Before/After 답변 |

### Knowledge Proposals API

| Endpoint | Method | 응답 | 용도 |
|----------|--------|------|------|
| `/api/v1/knowledge/proposals` | GET | 제안 목록 (현재 []) | 관계 테이블 |
| `/api/v1/knowledge/proposals/:id/approve` | POST | 501 (미구현) | 승인 버튼 |
| `/api/v1/knowledge/proposals/:id/reject` | POST | 501 (미구현) | 거부 버튼 |

---

## 3. 응답 구조 상세

### GET /api/v1/eval/full

```json
{
  "pattern_discovery": {
    "total_proposed": 0,
    "approved": 0,
    "rejected": 0,
    "pending": 0,
    "approval_rate": 0,
    "seed_relations": 34,
    "discovered_relations": 0,
    "relation_growth": 1.0,
    "by_type": {}
  },
  "answer_quality": {
    "total_analyses": 3,
    "used_discovered_link": 0,
    "discovered_usage_rate": 0,
    "session_history": [
      {"trace_id": "abc-123", "used_discovered": false},
      {"trace_id": "def-456", "used_discovered": false},
      {"trace_id": "ghi-789", "used_discovered": false}
    ]
  },
  "reasoning_coverage": {
    "causal_evidence_rate": 0.67,
    "full_coverage_cells": 9,
    "total_cells": 15,
    "full_coverage_rate": 0.6,
    "matrix": {
      "KR_sunscreen": {"causal": true, "data": true, "full": true},
      "KR_toner": {"causal": true, "data": true, "full": true},
      "KR_serum": {"causal": true, "data": true, "full": true},
      "KR_cream": {"causal": true, "data": true, "full": true},
      "KR_lip": {"causal": true, "data": false, "full": false},
      "JP_sunscreen": {"causal": true, "data": true, "full": true},
      "...": "..."
    }
  },
  "system_efficiency": {
    "status": "ok",
    "avg_cost_first_half": 0.033,
    "avg_cost_second_half": 0.031,
    "cost_reduction": 0.06,
    "total_sessions": 3,
    "sessions": [
      {"trace_id": "abc", "cost": 0.033, "created_at": "2026-03-30T..."},
      "..."
    ]
  },
  "before_after_pairs": []
}
```

### GET /api/v1/eval/before-after-pairs (PatternScout 구현 후)

```json
[
  {
    "query": "일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?",
    "before_trace_id": "abc-123",
    "before_answer": "비건은 클린뷰티 트렌드로 인해 인기가 높으며(58%), 무기자차는 UV차단 효과로 선호됩니다(47%).",
    "before_at": "2026-03-30T14:00:00",
    "after_trace_id": "def-456",
    "after_answer": "비건과 무기자차는 시너지 관계입니다. 실제 동시 비율(42%)이 독립 기대치(27%)보다 1.54배 높습니다...",
    "after_at": "2026-03-31T10:00:00"
  }
]
```

---

## 4. UI 구현 가이드

### 위치

기존 대시보드의 **BottomBar 위** 또는 **Zone B 상단**에 Knowledge Growth 바를 배치.
`[▼ 상세 보기]` 클릭 시 상세 패널이 Zone B 영역에 오버레이 또는 별도 탭으로 표시.

### 컴포넌트 구조

```
KnowledgeGrowthBar (상단 바 — 4축 요약)
├── AxisBadge × 4 (아이콘 + 라벨 + 수치)
└── ExpandButton ([▼ 상세 보기])

KnowledgeGrowthDetail (상세 패널)
├── AnswerQualityChart ⭐
│   └── Recharts LineChart
│       x축: 세션 (S1, S2, S3, ...)
│       y축: discovered_usage_rate (0~1)
│       데이터: answer_quality.session_history
│
├── ProposalTable
│   └── 테이블: 관계 타입, 상태, 승인/거부 버튼
│       데이터: GET /knowledge/proposals
│       현재: 빈 테이블 (Phase 2에서 채워짐)
│
├── CoverageMatrix
│   └── 3행(국가) × 5열(유형) 그리드
│       ●● = full (causal + data)
│       ●○ = partial (하나만)
│       ○○ = none
│       데이터: reasoning_coverage.matrix
│
└── BeforeAfterComparison ⭐
    └── 2-column 비교 카드
        왼쪽: Before 답변 (회색 배경)
        오른쪽: After 답변 (파랑 배경)
        데이터: GET /eval/before-after-pairs
        현재: 빈 상태 ("아직 비교할 데이터가 없습니다")
```

### 디자인 규칙 (기존 대시보드와 동일)

- Light theme, Linear 스타일
- border 기반 구분, shadow 최소
- 색상: 모노크롬 + MCP 서버 색상(파랑/녹색)
- 폰트: Inter (텍스트), JetBrains Mono (수치/JSON)
- shadcn/ui Card, Badge, Separator 사용

### 상태 처리

- **데이터 없음**: "아직 분석 이력이 없습니다" 메시지 표시
- **PatternScout 미구현**: 축 1/2 수치가 0인 것은 정상. "Phase 2에서 활성화됩니다" 라벨
- **Before/After 없음**: "동일 질문의 승인 전/후 답변이 축적되면 여기에 비교가 표시됩니다"

---

## 5. 참고 코드

| 파일 | 역할 | 참고 이유 |
|------|------|----------|
| `backend/eval/metrics.py` | 4축 메트릭 함수 | 응답 구조의 원본 |
| `backend/eval/snapshots.py` | 스냅샷 저장/비교 | compare 응답 구조 |
| `backend/api/routes_eval.py` | API 엔드포인트 | URL + 파라미터 |
| `frontend/src/lib/api.ts` | API 클라이언트 패턴 | 새 함수 추가 시 참고 |
| `frontend/src/components/bottom-bar.tsx` | 하단 바 패턴 | Knowledge Growth 바 위치 참고 |
| `frontend/src/components/result-panel.tsx` | Zone B 패턴 | 상세 패널 렌더링 참고 |
| `frontend/src/components/trace-panel.tsx` | Zone C 패턴 | 카드/뱃지 스타일 참고 |

### api.ts에 추가할 함수

```typescript
export const api = {
  // ... 기존 함수들 ...

  evalFull: () => fetchApi<EvalFullResult>("/eval/full"),
  evalBeforeAfter: () => fetchApi<BeforeAfterPair[]>("/eval/before-after-pairs"),
  knowledgeProposals: () => fetchApi<Proposal[]>("/knowledge/proposals"),
  approveProposal: (id: number) =>
    fetchApi(`/knowledge/proposals/${id}/approve`, { method: "POST" }),
  rejectProposal: (id: number) =>
    fetchApi(`/knowledge/proposals/${id}/reject`, { method: "POST" }),
};
```

---

## 6. 데이터 흐름

```
1. 페이지 로드 → GET /api/v1/eval/full → KnowledgeGrowthBar에 4축 표시
2. [상세 보기] 클릭 → KnowledgeGrowthDetail 표시
   - AnswerQualityChart: session_history → LineChart
   - CoverageMatrix: matrix → 3×5 그리드
   - ProposalTable: GET /knowledge/proposals → 테이블 (현재 빈)
   - BeforeAfterComparison: GET /eval/before-after-pairs → 비교 카드 (현재 빈)
3. TanStack Query로 30초 간격 자동 리프레시 (eval 데이터가 변하면 자동 반영)
```
