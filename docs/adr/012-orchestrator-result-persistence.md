# ADR-012: 오케스트레이터 결과 영속화 — orchestrator_results 테이블

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

`POST /ask`로 LLM 오케스트레이터를 실행하면 ReAct 루프가 도구를 자동 선택·호출하고 최종 답변을 생성한다. 이 결과는 프론트엔드의 Zone B(시각화 차트)와 Zone C(의사결정 트레이스)에 렌더링된다.

**문제**: 결과가 프론트엔드 `useState`에만 보관되어, 새로고침하거나 다른 질문으로 전환하면 유실된다. 동일한 질문을 다시 보려면 LLM을 재호출해야 하며, 이는 비용($0.01~0.03/건)과 시간(3~5초)을 낭비하고 결과 재현성도 보장하지 못한다.

기존 `tool_call_traces` 테이블에는 도구 호출 step이 저장되지만:
1. **최종 답변(answer)**: LLM의 종합 분석 텍스트가 DB에 기록되지 않음
2. **tool_output 10KB 제한**: 차트 렌더링에 필요한 전체 데이터가 잘려서 저장됨
3. **토큰 집계**: 전체 input/output 토큰 합계가 저장되지 않음

## 결정

**`orchestrator_results` 신규 테이블**을 추가하여 전체 결과를 저장한다. `tool_call_traces`와 역할을 분리한다.

```
tool_call_traces     — step별 디버깅/분석용 (10KB 제한 유지)
orchestrator_results — 완전한 결과 재생용 (제한 없음)
```

### 스키마

```sql
CREATE TABLE orchestrator_results (
    trace_id            VARCHAR(36)    PRIMARY KEY,
    user_query          TEXT           NOT NULL,
    answer              TEXT           NOT NULL,
    steps               JSONB          NOT NULL,     -- tool_output 포함 전체
    total_steps         INTEGER        NOT NULL,
    total_input_tokens  INTEGER        DEFAULT 0,
    total_output_tokens INTEGER        DEFAULT 0,
    total_cost_usd      NUMERIC(10,6)  DEFAULT 0,
    created_at          TIMESTAMPTZ    DEFAULT now()
);
```

### API 계약

```
POST /api/v1/orchestrator/ask        → 질문 실행 + 결과 자동 저장
GET  /api/v1/orchestrator/result/{id} → 저장된 결과 재조회 (POST /ask와 동일 형식)
GET  /api/v1/orchestrator/results     → 최근 결과 이력 목록
```

`GET /result/{id}`는 `POST /ask`와 완전히 동일한 `AskResponse` 형식을 반환하므로, 프론트엔드에서 코드 변경 없이 Zone B 시각화와 Zone C 트레이스를 완벽히 복원할 수 있다.

## 근거

### 왜 `tool_call_traces`를 확장하지 않는가?

- `tool_call_traces`는 `(trace_id, step)` 복합 PK로 설계된 step별 테이블이다.
- `answer`, `total_input_tokens` 같은 trace 단위 집계 데이터를 step 테이블에 넣으면 의미적 불일치가 생긴다.
- `tool_output` 10KB 제한은 디버깅 목적으로 적절하다. 차트 렌더링용 전체 데이터는 별도 경로로 관리하는 것이 맞다.

### 왜 steps를 JSONB 한 컬럼으로 저장하는가?

- `steps` 배열은 프론트엔드가 소비하는 정확한 형태 그대로다. 정규화하면 조인 복잡도만 올라간다.
- 이미 `tool_call_traces`에 정규화된 step별 데이터가 있으므로 이중 정규화는 불필요하다.
- PostgreSQL JSONB는 50~200KB 수준의 steps 데이터를 문제없이 처리한다.

### 저장 실패 시 ask() 응답에 영향 없음

`save_result()`는 try/except로 감싸져 있어 저장 실패가 사용자 응답을 차단하지 않는다. 에러 로그만 남기고 결과는 정상 반환된다.

## 영향

- Alembic 마이그레이션 002: 신규 테이블 추가 (기존 테이블 변경 없음)
- `TraceLogger`에 `save_result()`, `get_result()`, `get_recent_results()` 3개 메서드 추가
- `AskResponse`에 `total_input_tokens`, `total_output_tokens` 필드 추가 (기존 누락 수정)
- 프론트엔드: `api.getResult()`, `api.getResults()` 메서드 추가
