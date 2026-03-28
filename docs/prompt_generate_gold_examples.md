# Gold Example 생성 프롬프트

## 목적
Few-shot learning의 참고서이자 Eval 정답지로 사용될 Gold Example을 생성한다.
ChromaDB에 임베딩되어 벡터 검색의 소스가 되므로, 다양성과 정확성이 핵심이다.

## 제약 조건

### 브랜드 (Neo4j 시드 기준 4개 + 추가 확장)
- 이니스프리(Innisfree), 토리든(Torriden), 라운드랩(Roundlab), 스킨푸드(Skinfood)
- 추가: 코스알엑스(COSRX), 닥터지(Dr.G), 아누아(Anua), 메디힐(Mediheal), 비플레인(Beplain), 달바(d'Alba)

### 제품 유형 (5종)
- sunscreen, toner, serum, cream, lip

### 속성 스키마 (extracted_output)
```json
{
  "brand": "string — 한글 브랜드명",
  "productType": "sunscreen|toner|serum|cream|lip",
  "functionalClaims": ["UV차단", "수분공급", "진정", "브라이트닝", "피지조절", "항산화"],
  "valueClaims": ["비건", "클린뷰티", "동물실험프리", "무향", "저자극"],
  "keyIngredients": ["Neo4j Ingredient commonNameKo와 매칭되는 성분명"],
  "spf": "string (선크림 전용, eg. '50+')",
  "pa": "string (선크림 전용, eg. '++++')",
  "volume": "string (eg. '50ml', '200ml', '60매')",
  "additionalAttrs": {}
}
```

### 선크림 전용 속성
- `filterType`: "무기자차" | "유기자차" | "혼합자차"
- `spf`, `pa` 필수

### 토너/세럼 가능 속성
- `phType`: "약산성" (해당 시)
- `texture`: "워터", "에센스", "젤" 등

### lip 전용 속성
- `shade`: "#번호 컬러명"
- `texture`: "매트", "글로시", "벨벳", "코튼잉크" 등

## 생성 규칙

1. **제품 유형별 최소 6개**, 총 **40개 이상**
2. `raw_input`은 실제 이커머스 상품명 스타일 (브랜드 + 제품라인 + 핵심속성 + 용량)
3. 맥락 의존적 속성을 반드시 포함:
   - "무기자차"는 sunscreen에서만 filterType으로 추출
   - "약산성"은 toner에서만 phType으로 추출
   - "77"같은 숫자가 모델번호인 경우 vs 성분함량인 경우 구분
4. 마케팅 문구가 섞인 상품명도 포함 (eg. "[1+1]", "★베스트★", "NEW 리뉴얼")
5. `keyIngredients`는 Neo4j의 Ingredient 노드 commonNameKo와 매칭:
   나이아신아마이드, 히알루론산, 센텔라, 어성초, 녹차, 세라마이드, 징크옥사이드, 살리실산, 프로폴리스, 당근
6. `gold_id` 형식: `GOLD-{TYPE_PREFIX}-{NNN}` (eg. GOLD-SUN-001)
7. `quality_score`: 1.00 (시드이므로 최고 품질)
8. 트렌드 속성 포함: 마이크로바이옴, 프로바이오틱스, 병풀, 글루타치온 등 → additionalAttrs에

## 출력 형식
`seed_gold_examples.json` — JSON 배열
