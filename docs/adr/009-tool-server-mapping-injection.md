# ADR-009: 도구-서버 매핑을 하드코딩하지 않고 주입 방식으로 설계

- **상태**: accepted
- **날짜**: 2026-03-28

## 맥락

LLM 오케스트레이터가 도구를 호출한 뒤, 해당 도구가 어느 MCP 서버(kg/order)에 속하는지를 `tool_call_traces`에 기록해야 한다. 이 매핑을 어디에서 관리할 것인가?

## 검토한 대안

### A. TraceLogger에 하드코딩

```python
class TraceLogger:
    KG_TOOLS = {"query_causal_chain", "find_trending_ingredients", ...}

    def _resolve_server(self, tool_name):
        return "kg" if tool_name in self.KG_TOOLS else "order"
```

- 문제: 도구가 추가/제거될 때 TraceLogger를 수정해야 함
- 문제: TraceLogger가 서버 구성을 "알고 있어야" 함 — 관심사 분리 위반

### B. 각 서버 클래스에 TOOL_NAMES 상수 정의

```python
class KnowledgeGraphServer:
    TOOL_NAMES = {"query_causal_chain", ...}
```

- TraceLogger가 서버 클래스를 참조해야 함 — 순환 의존 위험

### C. 오케스트레이터가 매핑을 자동 생성하여 주입 (선택)

```python
# orchestrator가 서버별 도구를 등록할 때 매핑도 함께 생성
tool_to_server = {}
for name, fn in kg_tools.items():
    tool_to_server[name] = "kg"
for name, fn in order_tools.items():
    tool_to_server[name] = "order"

trace_logger = TraceLogger(engine, tool_to_server=tool_to_server)
```

## 결정

**C. 오케스트레이터가 매핑을 자동 생성하여 TraceLogger에 주입.**

TraceLogger는 `tool_to_server: dict[str, str]`을 init 시점에 받는다. 도구 이름과 서버 소속을 알 필요 없이, 주어진 매핑으로 `_resolve_server()`를 수행.

## 근거

1. **관심사 분리**: TraceLogger는 "기록"만 담당. 도구 구성은 오케스트레이터의 책임.
2. **단일 수정 지점**: 도구 추가/제거 시 오케스트레이터의 `tool_registry`만 수정. TraceLogger 코드 변경 불필요.
3. **테스트 용이**: 테스트에서 임의의 매핑을 주입하여 TraceLogger를 독립적으로 검증 가능.
4. **Phase 2 확장**: 새 MCP 서버(예: "external_api")가 추가되어도 매핑에 키만 추가.

## 결과

- **장점**: 도구 구성 변경이 TraceLogger에 전파되지 않음
- **장점**: 테스트에서 mock 매핑 주입으로 격리 가능
- **적용 위치**: `orchestrator/trace_logger.py` — `__init__(engine, tool_to_server)`
