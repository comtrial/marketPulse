# MarketPulse Gold Example 생성 명세서

> **이 문서의 목적**: 다른 AI 에이전트가 이 문서를 읽고, MarketPulse 속성 추출 시스템의 참고 사례(Gold Example) 50건을 정확하게 생성할 수 있도록 하는 완전한 명세.

---

## Gold Example이란 무엇인가

```
Gold Example = "이 상품명에서는 이 속성들을 이렇게 추출하면 정답이야"라는 검수된 사례.

역할 1 — 추출의 참고서:
  새 상품이 들어오면, 벡터 검색으로 유사한 Gold Example을 찾아서
  LLM에게 "이 예시처럼 추출해"라고 보여준다.
  LLM은 예시의 키 이름, 값 형식을 따라가므로 일관된 스키마로 추출된다.

역할 2 — 평가의 정답지:
  추출 정확도(F1)를 측정할 때, Gold Example이 정답 역할을 한다.
  50건 중 10건을 holdout test set으로 분리해서 시스템 평가에 사용.

따라서 Gold Example의 품질이 시스템 전체의 상한선을 결정한다.
키 이름, 값 형식, 추출 범위가 일관되고 정확해야 한다.
```

---

## 출력 형식

### 파일명
`seed_gold_examples.json`

### JSON 구조

```json
[
  {
    "id": "gold_001",
    "raw_input": "이니스프리 데일리 UV 프로텍션 크림 SPF50+ PA++++ 50ml 톤업 비건",
    "extracted_output": {
      "productType": "선크림",
      "brand": "이니스프리",
      "keyIngredients": [],
      "concentration": null,
      "volume": "50ml",
      "functionalClaims": ["톤업"],
      "valueClaims": ["비건"],
      "skinType": null,
      "spf": "50+",
      "pa": "++++",
      "additionalAttrs": {}
    },
    "product_type": "sunscreen",
    "brand": "Innisfree"
  }
]
```

---

## 속성 스키마 정의 (extracted_output의 구조)

### 고정 필드 — 모든 Gold Example에서 이 키 이름을 정확히 사용

| 필드명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `productType` | string | 제품 소분류 (한글) | `"선크림"`, `"토너"`, `"세럼"`, `"크림"`, `"립틴트"`, `"립밤"` |
| `brand` | string | 브랜드명 (한글) | `"이니스프리"`, `"토리든"`, `"라운드랩"`, `"스킨푸드"` |
| `keyIngredients` | string[] | 핵심 성분 목록. 간결한 한글명. | `["어성초", "히알루론산"]` |
| `concentration` | string \| null | 성분 함량 표기. 없으면 null. | `"77%"`, `"10%"`, `null` |
| `volume` | string \| null | 용량. 없으면 null. | `"250ml"`, `"50g"`, `"10매"`, `"4g"` |
| `functionalClaims` | string[] | 기능 클레임. 빈 배열 가능. | `["톤업", "수분", "진정"]` |
| `valueClaims` | string[] | 가치 클레임. 빈 배열 가능. | `["비건", "무향", "저자극"]` |
| `skinType` | string \| null | 대상 피부 타입. 없으면 null. | `"민감성"`, `"지성"`, `null` |
| `spf` | string \| null | SPF 수치. 선케어 아니면 null. | `"50+"`, `"30"`, `null` |
| `pa` | string \| null | PA 등급. 선케어 아니면 null. | `"++++"`, `"+++"`, `null` |
| `additionalAttrs` | object | 위 스키마 밖의 추가 속성. 빈 객체 가능. | `{"자차타입": "무기자차"}`, `{"컬러": "#09 코랄핑크"}` |

### 값 작성 규칙 (중요 — 일관성의 핵심)

```
1. keyIngredients:
   - 풀네임이 아닌 간결한 한글명 사용
   - ✅ "어성초"  ❌ "어성초 추출물"
   - ✅ "히알루론산"  ❌ "저분자 히알루론산 나트륨"  ❌ "Sodium Hyaluronate"
   - ✅ "나이아신아마이드"  ❌ "비타민 B3"
   - ✅ "센텔라"  ❌ "병풀 추출물"  ❌ "마데카소사이드" (이건 다른 성분)
   - ✅ "세라마이드"  ❌ "세라마이드 NP"
   - ✅ "녹차"  ❌ "카멜리아 시넨시스 잎 추출물"
   - 상품명에 성분이 명시적으로 언급되지 않으면 빈 배열 [].
     예: "이니스프리 UV 크림 SPF50+ 톤업" → keyIngredients: [] (성분 미언급)

2. functionalClaims — 허용 값 목록:
   "톤업", "노세범", "수분", "보습", "진정", "미백", "브라이트닝",
   "각질케어", "워터프루프", "자외선차단", "피부장벽", "항산화",
   "수분진정" (→ 이건 ["수분", "진정"]으로 분리)
   
   주의: "수분진정"처럼 합쳐진 키워드는 분리한다.
   "수분보습"은 의미가 비슷하므로 "수분"으로 통일.

3. valueClaims — 허용 값 목록:
   "비건", "저자극", "무향", "약산성", "산호초안전", "대용량"
   
   주의: "무기자차"는 valueClaims가 아니라 additionalAttrs에 넣는다.
   이유: 자차타입은 값이 "무기자차"/"유기자차"/"혼합"으로 분기하므로 
         별도 키-값 쌍이 적절.

4. additionalAttrs — 자주 등장하는 추가 속성:
   {"자차타입": "무기자차"} 또는 {"자차타입": "유기자차"}
   {"제형": "젤크림"} 또는 {"제형": "워터리"} 또는 {"제형": "매트"}
   {"컬러": "#09 코랄핑크"} — 립 제품
   {"마감": "매트"} 또는 {"마감": "글로시"} — 립 제품
   
   상품명에서 위 정규 필드로 커버되지 않는 정보가 있을 때만 사용.
   없으면 빈 객체 {}.

5. spf/pa:
   선크림이 아닌 제품은 반드시 null.
   "SPF50+" → spf: "50+"
   "PA++++" → pa: "++++"
   
6. skinType:
   상품명에 "민감성", "지성", "건성", "복합성" 등이 명시된 경우만.
   없으면 null. 추측하지 않는다.
```

---

## 50건 분포

```
sunscreen (선크림): 15건
  ├─ Innisfree 4건
  ├─ Torriden 4건
  ├─ Roundlab 4건
  └─ Skinfood 3건

toner (토너): 12건
  ├─ Innisfree 3건
  ├─ Torriden 3건
  ├─ Roundlab 3건
  └─ Skinfood 3건

serum (세럼/에센스): 10건
  ├─ Innisfree 3건
  ├─ Torriden 3건
  ├─ Roundlab 2건
  └─ Skinfood 2건

cream (크림): 8건
  ├─ Innisfree 2건
  ├─ Torriden 2건
  ├─ Roundlab 2건
  └─ Skinfood 2건

lip (립): 5건
  ├─ Innisfree 2건
  ├─ Torriden 1건
  ├─ Roundlab 1건
  └─ Skinfood 1건
```

---

## 필수 포함 사례 (패턴 검증용)

아래 사례들은 **반드시 포함**되어야 한다. 시스템 테스트의 핵심 케이스.

### 선크림 — 속성 조합 다양성 확보

```json
// gold_001: 기본 톤업 선크림 (가장 흔한 형태)
{
  "id": "gold_001",
  "raw_input": "이니스프리 데일리 UV 프로텍션 크림 SPF50+ PA++++ 50ml 톤업",
  "extracted_output": {
    "productType": "선크림",
    "brand": "이니스프리",
    "keyIngredients": [],
    "concentration": null,
    "volume": "50ml",
    "functionalClaims": ["톤업"],
    "valueClaims": [],
    "skinType": null,
    "spf": "50+",
    "pa": "++++",
    "additionalAttrs": {}
  },
  "product_type": "sunscreen",
  "brand": "Innisfree"
}

// gold_002: 비건 + 무기자차 (블루오션 조합)
{
  "id": "gold_002",
  "raw_input": "이니스프리 아쿠아 UV 프로텍션 크림 SPF50+ PA++++ 50ml 비건 무기자차 산호초안전",
  "extracted_output": {
    "productType": "선크림",
    "brand": "이니스프리",
    "keyIngredients": [],
    "concentration": null,
    "volume": "50ml",
    "functionalClaims": [],
    "valueClaims": ["비건", "산호초안전"],
    "skinType": null,
    "spf": "50+",
    "pa": "++++",
    "additionalAttrs": {"자차타입": "무기자차"}
  },
  "product_type": "sunscreen",
  "brand": "Innisfree"
}

// gold_003: 워터프루프 (SG에서 우세한 속성)
{
  "id": "gold_003",
  "raw_input": "토리든 다이브인 워터리 선크림 SPF50+ PA++++ 60ml 워터프루프 노세범 가벼운사용감",
  "extracted_output": {
    "productType": "선크림",
    "brand": "토리든",
    "keyIngredients": [],
    "concentration": null,
    "volume": "60ml",
    "functionalClaims": ["워터프루프", "노세범"],
    "valueClaims": [],
    "skinType": null,
    "spf": "50+",
    "pa": "++++",
    "additionalAttrs": {"제형": "워터리"}
  },
  "product_type": "sunscreen",
  "brand": "Torriden"
}
```

### 토너 — 성분+함량 추출 사례

```json
// gold_016: 성분 함량이 있는 토너
{
  "id": "gold_016",
  "raw_input": "토리든 다이브인 저분자 히알루론산 토너 300ml 수분 대용량",
  "extracted_output": {
    "productType": "토너",
    "brand": "토리든",
    "keyIngredients": ["히알루론산"],
    "concentration": null,
    "volume": "300ml",
    "functionalClaims": ["수분"],
    "valueClaims": ["대용량"],
    "skinType": null,
    "spf": null,
    "pa": null,
    "additionalAttrs": {}
  },
  "product_type": "toner",
  "brand": "Torriden"
}

// gold_017: 수치 함량이 있는 경우 (77%)
{
  "id": "gold_017",
  "raw_input": "스킨푸드 로열허니 프로폴리스 인리치드 토너 180ml 수분 보습",
  "extracted_output": {
    "productType": "토너",
    "brand": "스킨푸드",
    "keyIngredients": ["프로폴리스"],
    "concentration": null,
    "volume": "180ml",
    "functionalClaims": ["수분"],
    "valueClaims": [],
    "skinType": null,
    "spf": null,
    "pa": null,
    "additionalAttrs": {}
  },
  "product_type": "toner",
  "brand": "Skinfood"
}
```

### 립 — additionalAttrs에 컬러/마감 들어가는 사례

```json
// gold_046: 립틴트 (컬러 + 마감)
{
  "id": "gold_046",
  "raw_input": "이니스프리 비비드 코튼 잉크 틴트 4g #09 코랄핑크 매트",
  "extracted_output": {
    "productType": "립틴트",
    "brand": "이니스프리",
    "keyIngredients": [],
    "concentration": null,
    "volume": "4g",
    "functionalClaims": [],
    "valueClaims": [],
    "skinType": null,
    "spf": null,
    "pa": null,
    "additionalAttrs": {"컬러": "#09 코랄핑크", "마감": "매트"}
  },
  "product_type": "lip",
  "brand": "Innisfree"
}

// gold_048: 립밤 (기능 속성 있음)
{
  "id": "gold_048",
  "raw_input": "라운드랩 독도 립밤 12g 보습 비건",
  "extracted_output": {
    "productType": "립밤",
    "brand": "라운드랩",
    "keyIngredients": [],
    "concentration": null,
    "volume": "12g",
    "functionalClaims": ["보습"],
    "valueClaims": ["비건"],
    "skinType": null,
    "spf": null,
    "pa": null,
    "additionalAttrs": {}
  },
  "product_type": "lip",
  "brand": "Roundlab"
}
```

### 신규 속성 등장 사례 (패턴 E 대응)

```json
// gold_050: 마이크로바이옴 토너 (이 사례가 나중에 추가되는 것을 시뮬레이션)
// 참고: 이 사례는 초기 50건에 포함하되, 
//       "마이크로바이옴"이 additionalAttrs에 들어가는 형태.
//       나중에 정규 필드로 승격되면 이 gold도 업데이트됨.
{
  "id": "gold_050",
  "raw_input": "토리든 다이브인 마이크로바이옴 토너 200ml 유산균 피부장벽",
  "extracted_output": {
    "productType": "토너",
    "brand": "토리든",
    "keyIngredients": ["유산균"],
    "concentration": null,
    "volume": "200ml",
    "functionalClaims": ["피부장벽"],
    "valueClaims": [],
    "skinType": null,
    "spf": null,
    "pa": null,
    "additionalAttrs": {"성분카테고리": "마이크로바이옴"}
  },
  "product_type": "toner",
  "brand": "Torriden"
}
```

---

## 나머지 사례 생성 가이드

위에서 명시한 필수 사례 외의 나머지를 채울 때:

```
1. 각 브랜드 × 상품유형 조합마다 최소 1건 이상
2. 속성 풍부도를 다양하게:
   - 속성이 많은 사례 (8개+): 전체의 40%
   - 속성이 중간인 사례 (5~7개): 전체의 40%
   - 속성이 적은 사례 (3~4개): 전체의 20%
   
3. 핵심 속성 조합 커버:
   선크림: 톤업, 비건, 워터프루프, 무기자차, 노세범 조합들
   토너/세럼: 히알루론산, 센텔라, 나이아신아마이드, 어성초 등 성분 다양성
   크림: 보습, 진정, 피부장벽 등 기능 다양성
   립: 컬러+마감 조합, 립밤의 기능 속성

4. 반드시 섹션 "값 작성 규칙"을 따를 것
   특히 keyIngredients의 간결한 한글명 통일이 중요
```

---

## 검증 체크리스트

```
□ 총 50건
□ 모든 id가 "gold_001" ~ "gold_050" 형식
□ 모든 raw_input이 15자 이상
□ 모든 extracted_output에 productType 필드 존재
□ 선크림 사례에만 spf/pa가 non-null
□ 토너/세럼/크림/립 사례에서 spf/pa가 모두 null
□ keyIngredients가 항상 배열 (빈 배열 포함)
□ functionalClaims가 항상 배열
□ valueClaims가 항상 배열
□ additionalAttrs가 항상 객체 (빈 객체 포함)
□ "무기자차"가 valueClaims가 아닌 additionalAttrs에 있는지
□ 립틴트 사례에 컬러가 additionalAttrs에 있는지
□ 상품유형별 건수: sunscreen 15, toner 12, serum 10, cream 8, lip 5
□ 4개 브랜드가 골고루 분포
```

---

## 출력 요구사항

```
1. 최종 출력: seed_gold_examples.json (UTF-8, BOM 없음)
2. JSON 배열 형태, pretty-printed (indent=2)
3. 50건 정확히
4. id 순서대로 정렬
5. 생성 후 검증 체크리스트 수행 결과를 함께 보고
```
