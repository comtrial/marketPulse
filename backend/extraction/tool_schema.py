"""Tool Use schema for cosmetic attribute extraction.

구조 강제 역할: 키 이름과 타입을 보장한다.
값 형식 유도는 extractor.py의 system prompt(few-shot)가 담당.
"""

EXTRACTION_TOOL = {
    "name": "extract_cosmetic_attributes",
    "description": (
        "K-뷰티 화장품 상품명에서 구조화된 속성을 추출합니다. "
        "텍스트에 근거가 있는 속성만 추출하고, 추측하지 마세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "productType": {
                "type": "string",
                "description": "제품 소분류. 예: 선크림, 토너, 세럼, 에센스, 크림, 립틴트, 립밤",
            },
            "brand": {
                "type": "string",
                "description": "브랜드명. 한글로. 없으면 null",
            },
            "keyIngredients": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "핵심 성분 목록. 간결한 한글명. "
                    "'어성초 추출물'이 아닌 '어성초'. "
                    "'저분자 히알루론산 나트륨'이 아닌 '히알루론산'. "
                    "상품명에 성분이 명시되지 않으면 빈 배열 []."
                ),
            },
            "concentration": {
                "type": "string",
                "description": (
                    "주요 성분 함량. 예: '77%'. 없으면 null. "
                    "숫자만 보고 추측하지 말 것."
                ),
            },
            "volume": {
                "type": "string",
                "description": "제품 용량. 예: '250ml', '50g'. 없으면 null",
            },
            "functionalClaims": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "기능 클레임. 예: 톤업, 노세범, 수분, 진정, 미백, 각질케어, "
                    "워터프루프, 피부장벽, 항산화. "
                    "'수분진정'은 ['수분', '진정']으로 분리."
                ),
            },
            "valueClaims": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "가치 클레임. 예: 비건, 저자극, 무향, 약산성, 산호초안전, 대용량. "
                    "'무기자차'는 여기가 아니라 additionalAttrs에."
                ),
            },
            "skinType": {
                "type": "string",
                "description": "대상 피부 타입. 민감성, 지성, 건성, 복합성. 없으면 null.",
            },
            "spf": {
                "type": "string",
                "description": "SPF 수치. 선케어가 아니면 반드시 null.",
            },
            "pa": {
                "type": "string",
                "description": "PA 등급. 선케어가 아니면 반드시 null.",
            },
            "additionalAttrs": {
                "type": "object",
                "description": (
                    "위 스키마 밖의 추가 속성. 키-값 쌍. "
                    "예: {'자차타입': '무기자차'}, {'컬러': '#09 코랄핑크'}. "
                    "없으면 빈 객체 {}."
                ),
            },
        },
        "required": ["productType"],
    },
}
