# ADR-013: Zone B 도구 결과 시각화 — determineVisualizations 패턴

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

대시보드의 Zone B(결과 패널)가 Zone C(트레이스 패널)와 거의 동일한 텍스트 카드를 보여주고 있었다. 스펙(Doc 7 v3 3.2절)에 따르면 Zone B는 도구 결과를 **시각화**(차트, 히트맵, 인과 플로우)로 렌더링해야 하고, Zone C는 LLM의 **의사결정 과정**을 보여야 한다.

**문제**: 백엔드가 `tool_output_summary`(한 줄 텍스트)만 프론트엔드에 전달하고, `tool_output`(차트용 전체 JSON 데이터)은 DB에만 저장하고 있었다. 프론트엔드가 차트를 그릴 데이터가 없었다.

## 결정

### 1. 백엔드: steps에 tool_output 포함

오케스트레이터 steps 배열에 `tool_output`(전체 JSON)을 추가한다. `tool_output_summary`는 Zone C 트레이스용으로 유지한다.

```python
# tool_output: 프론트엔드 차트 렌더링용 전체 데이터
# tool_output_summary: Zone C 트레이스 패널용 한 줄 요약
all_steps.append({
    "tool_output": tool_output,          # 전체
    "tool_output_summary": summarize(),   # 한 줄
    ...
})
```

### 2. 프론트엔드: determineVisualizations() 자동 매핑

```typescript
function determineVisualizations(steps: OrchestratorStep[]): Visualization[] {
  for (const step of steps) {
    switch (step.tool) {
      case "get_attribute_trend":        → TrendChartView (Recharts LineChart)
      case "get_country_attribute_heatmap": → HeatmapView (색상 그리드)
      case "query_causal_chain":         → CausalChainView (인과 플로우)
      case "find_trending_ingredients":  → IngredientBarView (Recharts BarChart)
      case "find_ingredient_synergies":  → SynergyListView (뱃지 리스트)
    }
  }
}
```

도구가 추가되면 switch에 케이스를 추가하고 해당 시각화 컴포넌트만 구현하면 된다. tool_output이 없는 경우(이전 결과 등) fallback으로 텍스트 카드를 보여준다.

### 3. 도구별 시각화 매핑

| 도구 | 시각화 | 데이터 구조 |
|------|--------|-----------|
| `get_attribute_trend` | LineChart | `{trend: {JP: [{month, percentage}]}}` |
| `get_country_attribute_heatmap` | 히트맵 그리드 | `{matrix: {JP: {비건: 56.0}}}` |
| `query_causal_chain` | 인과 플로우 | `[{climate, skinConcern, function, chainStrength}]` |
| `find_trending_ingredients` | 수평 BarChart | `[{ingredient, productCount}]` |
| `find_ingredient_synergies` | 뱃지 리스트 | `[{partner, mechanism, source}]` |

## 근거

- **Zone B ≠ Zone C**: 두 존의 역할이 명확히 구분되어야 한다. Zone B = "무엇을 발견했는가" (시각화), Zone C = "어떻게 발견했는가" (사고 과정).
- **tool_output을 steps에 포함**: 별도 API 호출 없이 한 번의 `/ask` 응답으로 시각화까지 렌더링 가능.
- **Recharts 활용**: 이미 프로젝트에 설치된 라이브러리. 새 의존성 최소화.

## 영향

- `visualizations.tsx` 신규: 5개 시각화 컴포넌트 + determineVisualizations()
- `result-panel.tsx` 리팩터링: ToolResultCard → VisualizationRenderer
- `OrchestratorStep` 타입에 `tool_output?: unknown` 추가
- `markdown.tsx` 신규: LLM 최종 답변을 Markdown 형식으로 렌더링
