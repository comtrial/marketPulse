# ADR-019: query_causal_chain을 DISCOVERED_LINK 포함으로 확장

- **상태**: accepted
- **날짜**: 2026-03-30

## 맥락

PatternScout가 관계를 제안하고 사람이 승인해도, AnalystAgent의 query_causal_chain이 시드 경로만 읽으면 답변이 달라지지 않는다. 승인된 관계가 답변에 실제 반영되려면 query_causal_chain이 DISCOVERED_LINK도 반환해야 한다.

## 결정

**query_causal_chain의 반환 타입을 `list[dict]` → `dict`로 변경하여 시드 인과 체인과 DISCOVERED_LINK를 통합 반환한다.**

```python
# Before
return [{"climate": "...", "chainStrength": 0.81}, ...]

# After
return {
    "seed_chains": [{"climate": "...", "chainStrength": 0.81}, ...],
    "discovered_links": [{"fromConcept": "비건", "toConcept": "무기자차", "relationType": "SYNERGY", "evidence": {"lift": 1.54}}, ...]
}
```

## 영향 분석

| 영향받는 코드 | 현재 | 변경 | 하위 호환 |
|-------------|------|------|----------|
| `_summarize_output()` | `output[0]`으로 첫 체인 접근 | `output["seed_chains"][0]`으로 변경 | 수정 필요 |
| `_has_discovered_links()` | list/dict 양쪽 처리 | dict.get("discovered_links") | 이미 호환 |
| 프론트엔드 CausalChainView | tool_output이 list | tool_output.seed_chains | 수정 필요 |
| Before orchestrator_results | list로 저장됨 | 변경 안 됨 (이미 저장된 데이터) | 호환 |

## 근거

이 변경 없이는 PatternScout → 승인 → AnalystAgent 답변 개선의 **피드백 루프가 끊어진다.** 전체 시스템의 가치 명제("답변이 풍부해지고 있다")가 성립하려면 이 연결이 필수.

## 결과

- **장점**: 패턴 발견 → 승인 → 답변 반영의 완전한 루프
- **장점**: Eval 축 2(discovered_usage_rate)가 의미 있는 수치로 채워짐
- **단점**: 반환 타입 변경으로 기존 코드 수정 필요 (영향 범위 명확)
