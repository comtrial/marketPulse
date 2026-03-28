"""규칙 기반 추출 결과 검증 (LLM 호출 없음).

이 검증기가 보장하는 것:
  1. "없는 걸 만들어낸" 명백한 환각 감지 (확실한 것만)
  2. 타입/범위 같은 구조적 오류 감지

보장하지 않는 것:
  3. 의미적 정확성 (77이 농도인지 모델명인지) → Eval(gold 대비 F1)로 커버
  4. 누락 감지 (안 뽑은 것) → 사람 검수로 커버

errors vs warnings:
  errors = 확실한 오류. 이게 있으면 graph_sync 안 함.
  warnings = 의심. 통과는 시키되 로그로 남겨서 사후 분석 가능하게.

왜 교차 검증(크림+SPF)이 error가 아니라 warning인가:
  실제로 SPF가 있는 크림이 존재함 (선크림 겸용 크림).
  error로 잡으면 false positive → 운영 불가.
"""

import structlog

from extraction.schemas import ValidationResult

logger = structlog.get_logger()


class ExtractionValidator:

    def validate(self, attrs: dict, original_text: str) -> ValidationResult:
        """추출 결과를 규칙 기반으로 검증.

        Args:
            attrs: LLM이 추출한 속성 dict (tool_use 블록의 input)
            original_text: 원본 상품명 텍스트

        Returns:
            ValidationResult(passed, errors, warnings)
            passed = errors가 0건이면 True
        """
        errors: list[str] = []
        warnings: list[str] = []

        # ── errors: 확실한 오류 (graph_sync 차단) ──

        # 필수 필드: productType이 없으면 어떤 분석도 불가
        if not attrs.get("productType"):
            errors.append("필수 필드 누락: productType")

        # 타입 체크: 배열이어야 하는 필드가 문자열로 나오는 경우
        # Tool Use가 구조를 강제하지만, 드물게 타입이 깨질 수 있음
        for field in ["keyIngredients", "functionalClaims", "valueClaims"]:
            val = attrs.get(field)
            if val is not None and not isinstance(val, list):
                errors.append(
                    f"타입 오류: {field}이 배열이 아님 ({type(val).__name__})"
                )

        # SPF 범위: 1~100+ 밖이면 명백한 오류
        spf = attrs.get("spf")
        if spf:
            cleaned = spf.replace("+", "")
            try:
                if not (1 <= int(cleaned) <= 100):
                    errors.append(f"범위 오류: spf={spf}")
            except ValueError:
                errors.append(f"형식 오류: spf={spf}")

        # PA 형식: +, ++, +++, ++++ 만 유효
        pa = attrs.get("pa")
        if pa and pa not in ["+", "++", "+++", "++++"]:
            errors.append(f"형식 오류: pa={pa}")

        # ── warnings: 의심 (통과하되 로그) ──

        # 원본 텍스트를 정규화해서 비교 (공백 제거, 소문자)
        text_normalized = original_text.replace(" ", "").lower()

        # 성분 환각 의심: 추출된 성분이 원본에 아예 없으면 의심
        # "나이아신아마이드"를 추출했는데 원본에 없다 → LLM이 외부 지식을 사용했을 가능성
        for ingr in attrs.get("keyIngredients", []):
            ingr_normalized = ingr.replace(" ", "").lower()
            if ingr_normalized not in text_normalized:
                warnings.append(f"환각 의심: 성분 '{ingr}'가 원본에 없음")

        # SPF 환각 의심: 추출된 SPF 값이 원본에 없으면 의심
        if spf:
            cleaned = spf.replace("+", "")
            spf_patterns = [f"spf{cleaned}", f"spf {cleaned}", f"spf{spf}"]
            found = any(p in text_normalized for p in spf_patterns)
            if not found:
                warnings.append(f"환각 의심: spf={spf}가 원본에 없음")

        # 교차 의심: 토너/세럼 등에 SPF가 있으면 의심 (error 아닌 warning)
        # 크림+SPF는 실제로 존재하므로 크림은 제외
        ptype = (attrs.get("productType") or "").lower()
        spf_impossible_types = ["토너", "세럼", "에센스", "립틴트", "립밤", "립글로스"]
        if ptype in spf_impossible_types and attrs.get("spf"):
            warnings.append(f"교차 의심: {ptype}에 spf가 있음 (확인 필요)")

        passed = len(errors) == 0

        if warnings:
            logger.info(
                "extraction_warnings",
                product_text=original_text[:50],
                warnings=warnings,
            )
        if errors:
            logger.warning(
                "extraction_errors",
                product_text=original_text[:50],
                errors=errors,
            )

        return ValidationResult(passed=passed, errors=errors, warnings=warnings)
