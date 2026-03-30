# 비용-품질 트레이드오프 추적 — 백엔드 + 프론트엔드 작업 계획서

## 목표

PatternScout 추가 실행에 따른 비용 증가가 답변 품질 개선을 정당화하는지를 데이터로 보여준다.

---

## 1. 백엔드: eval_system_efficiency() 재설계

### 현재 문제

```python
# 현재: orchestrator_results.total_cost_usd만 보고 전반/후반 비교
# → "PatternScout 비용이 얼마인지", "그로 인해 답변이 좋아졌는지" 모름
```

### 재설계 — agent_type별 비용 분리 + 품질 연결

```python
def eval_system_efficiency(engine: Engine) -> dict:
    """비용-품질 트레이드오프 추적.

    세션별로:
      - analyst_cost: AnalystAgent 도구 호출 비용
      - scout_cost: PatternScout 도구 호출 비용
      - total_cost: 합계
      - used_discovered: 이 세션에서 DISCOVERED_LINK를 활용했는가

    이를 통해:
      - "discovered 활용 세션의 평균 비용" vs "미활용 세션의 평균 비용"
      - "PatternScout 추가 비용이 얼마인가"
      - "그 비용으로 답변이 실제로 달라졌는가"
    """
```

### 구현할 SQL

```sql
-- 세션별 agent_type별 비용 분리
WITH session_costs AS (
    SELECT
        t.trace_id,
        SUM(CASE WHEN t.agent_type = 'analyst' THEN t.cost_usd ELSE 0 END) AS analyst_cost,
        SUM(CASE WHEN t.agent_type = 'pattern_scout' THEN t.cost_usd ELSE 0 END) AS scout_cost,
        SUM(t.cost_usd) AS total_cost
    FROM tool_call_traces t
    GROUP BY t.trace_id
),
-- orchestrator_results에서 discovered 활용 여부
session_quality AS (
    SELECT
        r.trace_id,
        r.user_query,
        r.created_at,
        r.steps
    FROM orchestrator_results r
)
SELECT
    sc.trace_id,
    sq.user_query,
    sq.created_at,
    sc.analyst_cost,
    sc.scout_cost,
    sc.total_cost,
    sq.steps
FROM session_costs sc
JOIN session_quality sq ON sc.trace_id = sq.trace_id
ORDER BY sq.created_at
```

### 반환 구조

```json
{
    "status": "ok",
    "sessions": [
        {
            "trace_id": "abc-123",
            "user_query": "일본 비건 트렌드",
            "created_at": "2026-03-30T...",
            "analyst_cost": 0.052,
            "scout_cost": 0.068,
            "total_cost": 0.120,
            "used_discovered": false
        },
        {
            "trace_id": "def-456",
            "user_query": "비건+무기자차 함께 많은 이유",
            "created_at": "2026-03-30T...",
            "analyst_cost": 0.072,
            "scout_cost": 0.065,
            "total_cost": 0.137,
            "used_discovered": true
        }
    ],
    "summary": {
        "avg_analyst_cost": 0.062,
        "avg_scout_cost": 0.066,
        "avg_total_cost": 0.128,
        "scout_cost_ratio": 0.52,
        "with_discovered": {
            "count": 1,
            "avg_total_cost": 0.137
        },
        "without_discovered": {
            "count": 4,
            "avg_total_cost": 0.115
        },
        "quality_premium": 0.022
    }
}
```

`quality_premium` = discovered 활용 세션의 평균 비용 - 미활용 세션 평균 비용
→ "답변 품질 개선에 $0.022의 추가 비용이 발생"

---

## 2. 프론트엔드: 비용-품질 시각화

### 위치

Knowledge Growth 상세 보기의 4번째 축 (기존 "시스템 효율" 자리).

### 시각화 컴포넌트

```
┌─ 비용-품질 트레이드오프 ──────────────────────────────────────────┐
│                                                                   │
│  [세션별 비용 구성] ← Stacked BarChart                            │
│                                                                   │
│  $0.15 ┤  ┌──┐                                                   │
│  $0.10 ┤  │▓▓│  ┌──┐  ┌──┐  ┌──┐  ┌──┐                         │
│  $0.05 ┤  │░░│  │▓▓│  │░░│  │▓▓│  │░░│                         │
│  $0.00 ┤  └──┘  └──┘  └──┘  └──┘  └──┘                         │
│          S1     S2    S3     S4    S5                             │
│                        ↑ 승인                                     │
│                                                                   │
│  ░░ Analyst    ▓▓ PatternScout                                   │
│  ★ = DISCOVERED_LINK 활용 세션                                    │
│                                                                   │
│  ─── 요약 ───                                                     │
│  Analyst 평균: $0.062 | Scout 평균: $0.066                        │
│  Scout 비용 비중: 52%                                             │
│  품질 개선 추가 비용: +$0.022/세션                                 │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
GET /api/v1/eval/system-efficiency
→ eval_system_efficiency() (재설계된 버전)
→ sessions 배열 + summary

프론트엔드:
  sessions → Recharts StackedBarChart (analyst_cost + scout_cost)
  used_discovered=true인 세션에 ★ 마커
  summary → 요약 텍스트
```

---

## 3. 구현 순서

### 3.1: eval/metrics.py — eval_system_efficiency() 재작성

- tool_call_traces에서 agent_type별 비용 분리 집계
- orchestrator_results.steps에서 discovered 활용 여부 판별 (_has_discovered_links 재사용)
- sessions + summary 구조 반환

### 3.2: api/routes_eval.py — 기존 엔드포인트 그대로

GET /api/v1/eval/system-efficiency → 재설계된 함수 호출. 엔드포인트 변경 없음.

### 3.3: 프론트엔드 — CostTradeoffChart 컴포넌트

- knowledge-growth.tsx의 시스템 효율 섹션에 StackedBarChart 추가
- sessions 배열로 Analyst/Scout 비용 스택
- discovered 활용 세션 하이라이트
- summary 텍스트 렌더링

### 3.4: 단위 테스트

- eval_system_efficiency: agent_type별 분리 검증
- quality_premium 계산 검증
- sessions 없을 때 insufficient_data

---

## 4. 참고 코드

| 파일 | 참고 이유 |
|------|----------|
| `backend/eval/metrics.py` | eval_system_efficiency() 현재 구현 |
| `backend/eval/metrics.py::_has_discovered_links()` | discovered 판별 로직 재사용 |
| `backend/orchestrator/trace_logger.py` | tool_call_traces INSERT 구조 (agent_type 포함) |
| `frontend/src/components/knowledge-growth.tsx` | 기존 4축 UI 구조 |
| `frontend/src/lib/api.ts` | API 클라이언트 타입 |
