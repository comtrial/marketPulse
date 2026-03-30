# ADR-016: PatternScout를 AnalystAgent에서 분리

- **상태**: accepted
- **날짜**: 2026-03-30

## 맥락

Phase 2에서 주문 데이터의 통계적 패턴을 탐지하고 관계를 제안하는 기능이 필요하다. 이 기능을 기존 AnalystAgent에 추가할지, 별도 에이전트로 분리할지 결정해야 한다.

## 검토한 대안

### A. 하나의 에이전트에 통합

system prompt에 "질문 답변 + 패턴 탐지"를 모두 넣고, 도구 14개를 모두 제공.

문제:
1. "사용자 질문에 답하세요"와 "통계적 패턴을 탐지하세요"가 상충. 질문 답변 중 갑자기 propose_relationship 호출 위험.
2. 읽기 전용 에이전트에 쓰기 권한(propose_relationship)을 주면 의도치 않은 부작용.
3. MAX_STEPS를 12+로 올려야 하고, 한 번 질문에 $0.10+ 비용.
4. trace에서 "이건 질문 답변인가 패턴 탐지인가" 구분 불가 → Eval 불가.

### B. 별도 에이전트로 분리 (선택)

AnalystAgent: 읽기 도구 8개, 질문 답변, MAX_STEPS=5
PatternScout: 전체 도구 13개, 패턴 탐지, MAX_STEPS=7, agent_type="pattern_scout"

## 결정

**B. 별도 에이전트로 분리.** 목적이 다르면 에이전트가 달라야 한다.

## 근거

- system prompt 충돌 회피
- 읽기/쓰기 권한 분리 (최소 권한 원칙)
- 비용 제어 (각각 독립적 MAX_STEPS)
- Eval 분리 (agent_type으로 trace 구분)
- 트리거 차이: AnalystAgent=사용자 질문, PatternScout=매 분석 턴 완료 후

## 결과

- **장점**: 각 에이전트의 system prompt가 집중적이고 명확
- **장점**: agent_type으로 축 1(탐지)과 축 2(답변 품질)를 독립 측정
- **단점**: 코드 복잡도 증가 (두 에이전트 초기화·관리)
- **단점**: 매 턴 2번의 LLM 호출 (AnalystAgent + PatternScout)
