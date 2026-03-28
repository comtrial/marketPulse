# Architecture Decision Records

프로젝트의 주요 아키텍처 결정을 기록한다.
각 ADR은 `NNN-제목.md` 형식으로 이 디렉토리에 추가한다.

## 상태 정의
- **proposed**: 제안됨, 논의 필요
- **accepted**: 채택, 구현 진행
- **superseded**: 후속 결정으로 대체됨
- **deprecated**: 더 이상 유효하지 않음

## 템플릿

```markdown
# ADR-NNN: 제목

- **상태**: proposed | accepted | superseded | deprecated
- **날짜**: YYYY-MM-DD
- **대체**: (superseded인 경우) ADR-XXX

## 맥락
어떤 문제/상황에서 이 결정이 필요했는가

## 결정
무엇을 선택했는가

## 근거
왜 이 선택이 최선인가 (비교 대안 포함)

## 결과
이 결정으로 인해 발생하는 장단점, 후속 작업
```

## 목록

| ADR | 제목 | 상태 | 날짜 |
|-----|------|------|------|
| 001 | Neo4j 온톨로지 기반 지식 그래프 | accepted | 2026-03-27 |
| 002 | Golden Example few-shot 속성 추출 | accepted | 2026-03-27 |
| 003 | 자동 속성 승격 루프 | accepted | 2026-03-27 |
| 004 | MCP Server로 데이터 소스 노출 | accepted | 2026-03-27 |
| 005 | Tool Use + Few-Shot 2레이어 전략 | accepted | 2026-03-27 |
| 006 | Confidence 모듈 제거 | accepted | 2026-03-28 |
| 007 | SOLD_IN 관계에서 주문량 제거 | accepted | 2026-03-28 |
| 008 | Python 3.12 고정 (3.14 호환성) | accepted | 2026-03-28 |
