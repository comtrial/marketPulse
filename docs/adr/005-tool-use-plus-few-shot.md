# ADR-005: Tool Use + Dynamic Few-Shot 2레이어 전략

- **상태**: accepted
- **날짜**: 2026-03-27

## 맥락

LLM으로 속성을 추출할 때 두 가지 문제를 동시에 해결해야 한다:
1. **구조 일관성**: "functionalClaims"이 항상 string[]로 나와야 한다 (GROUP BY를 위해)
2. **값 형식 일관성**: "어성초 추출물"이 아니라 "어성초"로 나와야 한다 (집계를 위해)

## 결정

Tool Use와 Dynamic Few-Shot을 조합한 2레이어 전략을 사용한다.

- **Tool Use** → 구조 강제. 키 이름과 타입을 JSON Schema로 보장.
- **Few-Shot** → 값 형식 유도. 유사 사례의 추출 결과를 보여줘서 형식을 맞추게 함.

## 근거

Tool Use만으로도 구조는 해결됨. Tool description을 잘 쓰면 값 형식도 상당 부분 유도 가능. Few-shot의 추가 가치는 애매한 경계 케이스에서 효과적인 정도.

**그러나 Few-shot이 필수인 이유**: 새 카테고리가 추가되어도 gold example만 추가하면 되고(코드 변경 없음), 검수된 사례가 축적될수록 커버리지가 넓어지는 flywheel 구조.

| 대안 | 구조 | 값 형식 | 확장성 |
|------|------|---------|--------|
| Tool Use만 | 보장 | 부분적 | Tool description 수정 필요 |
| Few-shot만 | 보장 불가 | 가능 | 코드 변경 불필요 |
| **Tool Use + Few-shot (선택)** | 보장 | 가능 | 코드 변경 불필요 |
| LangChain Structured Output | 보장 | 가능 | 프레임워크 의존 |

LangChain은 사용하지 않음 — Anthropic SDK 직접 사용이 파이프라인을 완전히 제어 가능.

## 결과

- **장점**: 1,000건 추출 후 GROUP BY가 깨끗하게 동작
- **장점**: 프롬프트를 파일로 분리 (prompts/extractor/v1.txt) — 코드 변경 없이 프롬프트 이터레이션
- **장점**: model 파라미터로 haiku/sonnet 교체 가능 — 비용/정확도 트레이드오프
- **단점**: few-shot example 품질이 추출 품질의 상한선
