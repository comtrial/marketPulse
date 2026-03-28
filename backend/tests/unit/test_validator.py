"""ExtractionValidator 단위 테스트.

테스트 범주:
  1. errors — 확실한 오류 (graph_sync 차단)
  2. warnings — 의심 (통과하되 로그)
  3. 정상 통과 — errors/warnings 모두 없음
"""

import pytest

from extraction.validator import ExtractionValidator


@pytest.fixture
def validator():
    return ExtractionValidator()


# ── errors: 확실한 오류 ──


class TestErrors:

    def test_missing_product_type(self, validator):
        """productType이 없으면 error."""
        attrs = {"brand": "토리든", "keyIngredients": []}
        result = validator.validate(attrs, "토리든 선크림")

        assert not result.passed
        assert any("productType" in e for e in result.errors)

    def test_empty_product_type(self, validator):
        """productType이 빈 문자열이면 error."""
        attrs = {"productType": "", "brand": "토리든"}
        result = validator.validate(attrs, "토리든 선크림")

        assert not result.passed

    def test_array_field_not_array(self, validator):
        """keyIngredients가 배열이 아닌 문자열이면 error."""
        attrs = {
            "productType": "선크림",
            "keyIngredients": "히알루론산",  # 배열이어야 함
        }
        result = validator.validate(attrs, "토리든 히알루론산 선크림")

        assert not result.passed
        assert any("배열이 아님" in e for e in result.errors)

    def test_functional_claims_not_array(self, validator):
        """functionalClaims가 배열이 아니면 error."""
        attrs = {
            "productType": "선크림",
            "functionalClaims": "UV차단",  # 배열이어야 함
        }
        result = validator.validate(attrs, "토리든 선크림")

        assert not result.passed

    def test_spf_out_of_range(self, validator):
        """SPF가 100 초과이면 error."""
        attrs = {"productType": "선크림", "spf": "500"}
        result = validator.validate(attrs, "선크림 SPF500")

        assert not result.passed
        assert any("범위 오류" in e for e in result.errors)

    def test_spf_invalid_format(self, validator):
        """SPF가 숫자가 아니면 error."""
        attrs = {"productType": "선크림", "spf": "높음"}
        result = validator.validate(attrs, "선크림 SPF높음")

        assert not result.passed
        assert any("형식 오류" in e for e in result.errors)

    def test_pa_invalid_format(self, validator):
        """PA가 +/++/+++/++++ 이외이면 error."""
        attrs = {"productType": "선크림", "pa": "+++++"}
        result = validator.validate(attrs, "선크림 PA+++++")

        assert not result.passed
        assert any("형식 오류" in e for e in result.errors)

    def test_multiple_errors(self, validator):
        """여러 error가 동시에 발생하는 경우."""
        attrs = {
            "keyIngredients": "히알루론산",  # 배열 아님
            "spf": "999",  # 범위 초과
            "pa": "+++++",  # 형식 오류
        }
        result = validator.validate(attrs, "선크림 SPF999")

        assert not result.passed
        assert len(result.errors) >= 3  # productType 누락 + 배열 + SPF + PA


# ── warnings: 의심 ──


class TestWarnings:

    def test_ingredient_hallucination(self, validator):
        """원본에 없는 성분이 추출되면 warning."""
        attrs = {
            "productType": "토너",
            "keyIngredients": ["히알루론산", "나이아신아마이드"],
        }
        # 원본에는 히알루론산만 있고 나이아신아마이드는 없음
        result = validator.validate(attrs, "라운드랩 히알루론산 토너 200ml")

        assert result.passed  # warning이지 error가 아님
        assert any("나이아신아마이드" in w for w in result.warnings)

    def test_spf_hallucination(self, validator):
        """원본에 없는 SPF 값이 추출되면 warning."""
        attrs = {"productType": "선크림", "spf": "30"}
        result = validator.validate(attrs, "이니스프리 UV 디펜스 선크림 SPF50+")

        assert result.passed  # SPF 형식은 유효하니까 error 아님
        assert any("spf=30" in w for w in result.warnings)

    def test_cross_type_suspicion(self, validator):
        """토너에 SPF가 있으면 warning (error 아님)."""
        attrs = {"productType": "토너", "spf": "50"}
        result = validator.validate(attrs, "토너 SPF50")

        assert result.passed  # 교차 의심은 warning
        assert any("교차 의심" in w for w in result.warnings)

    def test_cream_with_spf_no_warning(self, validator):
        """크림에 SPF가 있어도 교차 의심 warning이 나지 않음 (실제로 존재)."""
        attrs = {"productType": "크림", "spf": "15"}
        result = validator.validate(attrs, "올인원 크림 SPF15")

        assert result.passed
        cross_warnings = [w for w in result.warnings if "교차 의심" in w]
        assert len(cross_warnings) == 0


# ── 정상 통과 ──


class TestPass:

    def test_sunscreen_full_attrs(self, validator):
        """선크림 전체 속성이 정상인 경우."""
        attrs = {
            "productType": "선크림",
            "brand": "토리든",
            "keyIngredients": ["히알루론산", "징크옥사이드"],
            "functionalClaims": ["UV차단", "수분공급"],
            "valueClaims": ["비건"],
            "spf": "50+",
            "pa": "++++",
            "volume": "60ml",
            "additionalAttrs": {"자차타입": "무기자차"},
        }
        text = "토리든 다이브인 무기자차 히알루론산 징크옥사이드 선크림 SPF50+ PA++++ 60ml 비건"
        result = validator.validate(attrs, text)

        assert result.passed
        assert len(result.errors) == 0

    def test_toner_minimal(self, validator):
        """토너 최소 속성 — productType만 있어도 통과."""
        attrs = {"productType": "토너"}
        result = validator.validate(attrs, "라운드랩 토너")

        assert result.passed
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_none_fields_ok(self, validator):
        """spf, pa 등이 None이면 에러 아님."""
        attrs = {
            "productType": "세럼",
            "brand": "토리든",
            "spf": None,
            "pa": None,
        }
        result = validator.validate(attrs, "토리든 세럼")

        assert result.passed
