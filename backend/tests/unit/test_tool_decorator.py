"""@tool 데코레이터 단위 테스트.

검증 범위:
  1. Pydantic 모델에서 Anthropic Tool 스키마가 정확히 생성되는지
  2. docstring이 description으로 추출되는지
  3. dict 입력 → Pydantic 변환 + 검증이 동작하는지
  4. collect_tool_schemas/collect_tool_registry가 @tool 메서드를 정확히 수집하는지
  5. 잘못된 입력에 대해 Pydantic ValidationError가 발생하는지
"""

from typing import Literal

import pytest
from pydantic import BaseModel, Field, ValidationError

from orchestrator.tool_decorator import (
    collect_tool_registry,
    collect_tool_schemas,
    tool,
)


# ── 테스트용 서버 클래스 ──


class DummyInput(BaseModel):
    country: Literal["KR", "JP", "SG"] = Field(description="국가 코드")
    top_k: int = Field(default=5, description="상위 N개")


class DummyServer:

    @tool(DummyInput)
    def my_tool(self, params: DummyInput) -> dict:
        """더미 도구 설명."""
        return {"country": params.country, "top_k": params.top_k}

    def not_a_tool(self):
        """@tool이 없는 일반 메서드."""
        return "hello"


# ── 스키마 생성 테스트 ──


class TestSchemaGeneration:

    def test_schema_has_correct_name(self):
        schemas = collect_tool_schemas(DummyServer())
        assert len(schemas) == 1
        assert schemas[0]["name"] == "my_tool"

    def test_schema_description_from_docstring(self):
        schemas = collect_tool_schemas(DummyServer())
        assert schemas[0]["description"] == "더미 도구 설명."

    def test_schema_has_properties(self):
        schemas = collect_tool_schemas(DummyServer())
        props = schemas[0]["input_schema"]["properties"]
        assert "country" in props
        assert "top_k" in props

    def test_schema_country_has_enum(self):
        schemas = collect_tool_schemas(DummyServer())
        props = schemas[0]["input_schema"]["properties"]
        assert props["country"]["enum"] == ["KR", "JP", "SG"]

    def test_schema_required_fields(self):
        schemas = collect_tool_schemas(DummyServer())
        required = schemas[0]["input_schema"].get("required", [])
        assert "country" in required

    def test_non_tool_methods_excluded(self):
        """@tool이 없는 메서드는 수집되지 않음."""
        schemas = collect_tool_schemas(DummyServer())
        names = [s["name"] for s in schemas]
        assert "not_a_tool" not in names


# ── 레지스트리 수집 테스트 ──


class TestRegistryCollection:

    def test_registry_has_tool(self):
        registry = collect_tool_registry(DummyServer())
        assert "my_tool" in registry
        assert callable(registry["my_tool"])

    def test_registry_excludes_non_tool(self):
        registry = collect_tool_registry(DummyServer())
        assert "not_a_tool" not in registry


# ── 실행 시 Pydantic 변환 테스트 ──


class TestToolExecution:

    def test_dict_input_converted_to_pydantic(self):
        """오케스트레이터가 dict로 호출 → Pydantic 모델로 변환됨."""
        server = DummyServer()
        result = server.my_tool({"country": "JP", "top_k": 3})
        assert result == {"country": "JP", "top_k": 3}

    def test_default_value_applied(self):
        """top_k 누락 시 기본값 5 적용."""
        server = DummyServer()
        result = server.my_tool({"country": "KR"})
        assert result == {"country": "KR", "top_k": 5}

    def test_invalid_enum_raises_error(self):
        """Literal에 없는 값이면 ValidationError."""
        server = DummyServer()
        with pytest.raises(ValidationError):
            server.my_tool({"country": "XX"})

    def test_missing_required_raises_error(self):
        """필수 필드 누락 시 ValidationError."""
        server = DummyServer()
        with pytest.raises(ValidationError):
            server.my_tool({})
