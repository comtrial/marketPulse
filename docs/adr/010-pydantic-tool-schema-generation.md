# ADR-010: Pydantic 모델 기반 도구 스키마 자동 생성

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

LLM 오케스트레이터가 8개 도구를 Anthropic Tool 형식으로 LLM에 전달해야 한다. 각 도구에는 `name`, `description`, `input_schema`(JSON Schema)가 필요하다.

초기 구현에서 이 스키마를 수동으로 작성하면 300줄+ 의 반복적 JSON 정의가 되고, 함수 시그니처가 변경될 때 스키마와의 동기화가 깨지는 문제가 발생한다.

## 검토한 대안

### A. 수동 JSON 스키마 (llm_orchestrator.py 내부)

```python
self.tools = [
    {"name": "query_causal_chain", "description": "...",
     "input_schema": {"type": "object", "properties": {"country_code": {"type": "string", ...}}}},
    # × 8개 도구 = 300줄+
]
```

- 문제: 함수 시그니처와 스키마가 분리되어 동기화 깨짐 위험
- 문제: 도구 추가 시 3곳 수정 (함수, 스키마, 레지스트리)
- 문제: 입력 검증 없음 — LLM이 잘못된 타입을 보내도 런타임에서야 발견

### B. 별도 JSON/YAML 파일

- 문제: 파일과 코드 사이 동기화가 여전히 수동
- 문제: 런타임 타입 검증 불가

### C. Pydantic BaseModel + @tool 데코레이터 (선택)

```python
class QueryCausalChainInput(BaseModel):
    country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")

@tool(QueryCausalChainInput)
def query_causal_chain(self, params: QueryCausalChainInput) -> list[dict]:
    """특정 국가의 인과 체인을 반환."""
    ...
```

## 결정

**Pydantic BaseModel로 도구 입력을 정의하고, `@tool` 데코레이터로 Anthropic Tool 스키마를 자동 생성한다.**

### 동작 원리

1. **정의 시점**: `model_json_schema()` → Anthropic `input_schema` 자동 생성
2. **정의 시점**: 함수 `__doc__` → Tool `description` (중복 제거)
3. **수집 시점**: `collect_tool_schemas(server)` → 서버의 모든 @tool 메서드에서 스키마 일괄 수집
4. **호출 시점**: LLM이 보낸 dict → Pydantic 모델로 변환 + 타입 검증 → 원래 함수 실행

### 단일 수정 지점 원칙

도구를 추가/수정할 때 **서버 파일 1곳만** 수정:
- Pydantic 모델(입력 타입) + 함수(로직) + docstring(설명)
- 오케스트레이터 코드 수정 불필요

## 구현 파일

- `orchestrator/tool_decorator.py`: `@tool` 데코레이터 + `collect_tool_schemas()` + `collect_tool_registry()`
- `mcp_servers/kg_server.py`: 4개 도구에 @tool 적용
- `mcp_servers/order_server.py`: 4개 도구에 @tool 적용
- `orchestrator/llm_orchestrator.py`: `_register_server()`에서 자동 수집

## 근거

| 기준 | 수동 스키마 | Pydantic + @tool |
|------|-----------|-----------------|
| 동기화 | 수동, 깨지기 쉬움 | 자동, 단일 진실 소스 |
| 입력 검증 | 없음 | Pydantic 런타임 검증 |
| 도구 추가 시 수정 | 3곳 (함수+스키마+레지스트리) | 1곳 (서버 파일) |
| 코드량 | 300줄+ JSON | 입력 모델당 3-5줄 |
| description 관리 | 스키마 내 문자열 | docstring (IDE 지원) |

이 패턴은 FastMCP, OpenAI function calling, LangChain Tool 등 실무에서 공통적으로 사용되는 best practice.

## 결과

- **장점**: 도구 함수와 스키마가 같은 파일에서 관리 — 동기화 실수 제거
- **장점**: Literal, Field(description=...) 등 Pydantic 타입 시스템으로 enum, 기본값, 설명 표현
- **장점**: 런타임 입력 검증 — LLM이 잘못된 타입을 보내면 Pydantic ValidationError로 조기 감지
- **장점**: IDE 자동완성/타입 체크가 도구 입력에 대해 동작
- **후속**: 새 서버(Phase 2)를 추가할 때 `_register_server("new", new_server)`만 호출
