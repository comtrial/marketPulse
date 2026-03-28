"""도구 정의 데코레이터 — Pydantic 모델에서 Anthropic Tool 스키마를 자동 생성.

실무 best practice:
  1. 도구 입력을 Pydantic BaseModel로 정의 → model_json_schema()가 input_schema 자동 생성
  2. 함수의 docstring → Tool의 description (중복 제거)
  3. 런타임에 Pydantic이 입력 검증 (타입 오류 조기 감지)

이전 방식 (수동 스키마 300줄):
    {"name": "query_causal_chain", "description": "...", "input_schema": {"type": "object", ...}}

현재 방식 (Pydantic + 데코레이터):
    class QueryCausalChainInput(BaseModel):
        country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")

    @tool(QueryCausalChainInput)
    def query_causal_chain(self, params):
        '''특정 국가의 인과 체인을 반환.'''
        ...

    → 스키마 자동 생성, docstring이 description, Pydantic이 입력 검증.
"""

from functools import wraps
from typing import Any

from pydantic import BaseModel


# 도구 메타데이터를 함수에 부착하는 어트리뷰트 이름
_TOOL_ATTR = "_tool_meta"


def tool(input_model: type[BaseModel]):
    """도구 데코레이터. Pydantic 모델을 받아 Anthropic Tool 스키마를 자동 생성.

    Usage:
        class MyInput(BaseModel):
            country_code: Literal["KR", "JP", "SG"] = Field(description="국가 코드")

        @tool(MyInput)
        def my_tool(self, params: MyInput) -> dict:
            '''도구 설명 — 이 docstring이 Tool description이 됨.'''
            return {"result": params.country_code}

    데코레이터가 하는 일:
      1. 함수에 _tool_meta 어트리뷰트 부착 (이름, 스키마, 입력 모델)
      2. 호출 시 dict 입력을 Pydantic 모델로 변환 + 검증
      3. 검증 통과한 모델 인스턴스를 함수에 전달
    """

    def decorator(fn):
        # Pydantic model_json_schema()로 Anthropic input_schema 생성
        schema = input_model.model_json_schema()

        # Pydantic v2의 model_json_schema()는 $defs, title 등을 포함하므로 정리
        # Anthropic Tool은 type, properties, required만 필요
        cleaned_schema = {
            "type": "object",
            "properties": schema.get("properties", {}),
        }
        if "required" in schema:
            cleaned_schema["required"] = schema["required"]

        # $defs가 있는 경우 (중첩 모델) 풀어서 넣기
        if "$defs" in schema:
            cleaned_schema["$defs"] = schema["$defs"]

        # 함수에 메타데이터 부착
        setattr(fn, _TOOL_ATTR, {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip(),
            "input_schema": cleaned_schema,
            "input_model": input_model,
        })

        @wraps(fn)
        def wrapper(self_or_first, raw_input: dict | BaseModel | Any = None, **kwargs):
            # 오케스트레이터가 dict로 호출 → Pydantic 모델로 변환 + 검증
            if isinstance(raw_input, dict):
                params = input_model(**raw_input)
            elif isinstance(raw_input, input_model):
                params = raw_input
            elif raw_input is None and kwargs:
                # keyword argument로 호출된 경우
                params = input_model(**kwargs)
            else:
                params = raw_input

            return fn(self_or_first, params)

        # 메타데이터를 wrapper에도 전파
        setattr(wrapper, _TOOL_ATTR, getattr(fn, _TOOL_ATTR))
        return wrapper

    return decorator


def collect_tool_schemas(server_instance: object) -> list[dict]:
    """서버 인스턴스에서 @tool 데코레이터가 붙은 메서드들의 Anthropic Tool 스키마를 수집.

    Returns:
        [{"name": "...", "description": "...", "input_schema": {...}}, ...]
    """
    schemas = []
    for attr_name in dir(server_instance):
        attr = getattr(server_instance, attr_name, None)
        if callable(attr) and hasattr(attr, _TOOL_ATTR):
            meta = getattr(attr, _TOOL_ATTR)
            schemas.append({
                "name": meta["name"],
                "description": meta["description"],
                "input_schema": meta["input_schema"],
            })
    return schemas


def collect_tool_registry(server_instance: object) -> dict[str, callable]:
    """서버 인스턴스에서 @tool 데코레이터가 붙은 메서드들의 이름→함수 매핑을 수집.

    Returns:
        {"query_causal_chain": <bound method>, ...}
    """
    registry = {}
    for attr_name in dir(server_instance):
        attr = getattr(server_instance, attr_name, None)
        if callable(attr) and hasattr(attr, _TOOL_ATTR):
            meta = getattr(attr, _TOOL_ATTR)
            registry[meta["name"]] = attr
    return registry
