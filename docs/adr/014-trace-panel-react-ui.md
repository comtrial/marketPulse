# ADR-014: Zone C 트레이스 패널 — ReAct Think/Act/Observe 시각화

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

Zone C는 LLM의 의사결정 과정을 보여주는 트레이스 패널이다. 면접 데모 시 "LLM이 질문에 따라 다른 도구를 자동 선택한다"는 것을 3분 내에 증명해야 한다(Doc 7 설계 원칙 #1, #4).

기존 구현은 단순한 카드 나열이었다. LangSmith, Langfuse, prompt-kit 등의 업계 표준 UI 패턴을 조사하여 고도화했다.

## 결정

### ReAct 3단계 시각 구분

각 step을 Think → Act → Observe 세 단계로 시각적으로 분리하여 LLM의 사고 과정을 명확히 드러낸다.

```
┌─ Think ─────────────────────────────┐  amber 배경
│ "비율 추이를 먼저 확인하여          │
│  상승 중인지 검증하겠습니다."        │
└─────────────────────────────────────┘
┌─ Act ───────────────────────────────┐  서버 색상 보더
│ get_attribute_trend                  │
│ ▸ Parameters: {attribute: "비건"...} │
└─────────────────────────────────────┘
┌─ Observe ───────────────────────────┐  sky 배경
│ JP: 19.0%→56.0%, SG: 32.1%→38.4%   │  ← 숫자 하이라이트
│ ▸ Full Response (dark JSON toggle)   │
└─────────────────────────────────────┘
  ██████████░░░░░░░░  1,203ms          ← latency 워터폴
```

### 적용한 UI 패턴

| 패턴 | 레퍼런스 | 적용 |
|------|---------|------|
| Timeline + numbered dots | LangSmith, Langfuse | 세로 연결선 + MCP 서버별 색상 도트 |
| Latency waterfall bar | Langfuse Timeline View | Step별 비율 기반 수평 바 |
| Think/Act/Observe triptych | ReAct 논문, prompt-kit | 3단계 별도 배경색 + 배지 |
| Staggered step reveal | FlowToken | CSS keyframe 150ms 간격 fade-in |
| Number highlighting | 자체 설계 | Observe 영역의 숫자를 정규식으로 bold 처리 |
| Dark-themed JSON toggle | Braintrust | 터미널 스타일 (gray-900 + emerald-400) |
| Token usage grid | Datadog, Langfuse | Input/Output/Cost 3칸 그리드 |
| Server distribution stacked bar | 자체 설계 | MCP 서버별 비율 + 레이턴시 분포 |

### MCP 서버 색상 체계

| 서버 | DB | 색상 | 의미 |
|------|-----|------|------|
| order | PostgreSQL | 파란색 | "얼마나?" — 수치, 집계 |
| kg | Neo4j | 녹색 | "왜?" — 인과, 그래프 |
| vector | ChromaDB | 보라색 | "비슷한?" — 유사도 |
| llm | Claude | 주황색 | "판단" — 종합, 생성 |

## 근거

- **면접 데모 임팩트**: Think 블록이 시각적으로 강조되면 "LLM이 추론하고 있다"는 것이 즉시 전달된다.
- **기술력 증명**: Latency 워터폴, 토큰 그리드, 서버 분포 바가 엔지니어링 깊이를 보여준다.
- **업계 표준 준수**: LangSmith/Langfuse의 trace 시각화 패턴을 따라 기술적 신뢰감을 준다.

## 영향

- `trace-panel.tsx` 전면 재작성
- `globals.css`에 step-reveal 애니메이션 추가
- `markdown.tsx` 신규: reasoning 텍스트 Markdown 렌더링
- `react-markdown`, `remark-gfm` 패키지 추가
