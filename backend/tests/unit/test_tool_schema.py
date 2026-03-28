"""Tool schema 구조 검증 테스트."""

from extraction.tool_schema import EXTRACTION_TOOL


def test_tool_name():
    assert EXTRACTION_TOOL["name"] == "extract_cosmetic_attributes"


def test_required_fields():
    """productType이 required에 포함되어야 함."""
    required = EXTRACTION_TOOL["input_schema"]["required"]
    assert "productType" in required


def test_array_fields_are_array_type():
    """keyIngredients, functionalClaims, valueClaims는 array 타입이어야 함."""
    props = EXTRACTION_TOOL["input_schema"]["properties"]
    for field in ["keyIngredients", "functionalClaims", "valueClaims"]:
        assert props[field]["type"] == "array"
        assert props[field]["items"]["type"] == "string"


def test_additional_attrs_is_object():
    """additionalAttrs는 object 타입이어야 함."""
    props = EXTRACTION_TOOL["input_schema"]["properties"]
    assert props["additionalAttrs"]["type"] == "object"


def test_all_expected_fields_present():
    """Doc 3 스펙의 모든 필드가 존재하는지."""
    props = EXTRACTION_TOOL["input_schema"]["properties"]
    expected = [
        "productType", "brand", "keyIngredients", "concentration",
        "volume", "functionalClaims", "valueClaims", "skinType",
        "spf", "pa", "additionalAttrs",
    ]
    for field in expected:
        assert field in props, f"Missing field: {field}"
