# [Doc 8-C] 테스트 시나리오 + 데이터 생성 요구서

> **이 문서의 목적**: PatternScout의 Before/After를 데모하기 위해 어떤 데이터가 필요한지 정의한다. 실제 데이터 생성은 다른 세션/에이전트가 이 문서를 참조하여 수행.

> **핵심**: PatternScout는 구조화된 절차(속성 조회 → lift 계산 → 상관 계산 → 비교)를 따른다. 데이터에 이 절차로 발견 가능한 패턴이 심어져 있어야 한다. 동시에 시드 온톨로지에는 그 관계가 없어야 한다("발견"이 되려면).

---

## 1. 데이터에 심어야 하는 패턴 — 3개 확정 + 1개 보너스

### 패턴 G: SYNERGY (JP sunscreen 비건+무기자차)

```
PatternScout 절차 Step 3에서 발견됨.
  → compute_cooccurrence_lift("비건", "무기자차", "JP", "sunscreen")

데이터 조건:
  JP sunscreen ~180건에서:
    비건 단독: ~58% (패턴 A 유지)
    무기자차 단독: ~47%
    비건+무기자차 동시: ~42% (의도적 초과)
    lift = 42 / (58×47/100) = 1.54

  구체적 분포 (180건 기준):
    비건O + 무기자차O: 76건 (42%)
    비건O + 무기자차X: 28건 (16%)
    비건X + 무기자차O: 9건 (5%)
    비건X + 무기자차X: 67건 (37%)

시드에 없는 것: (비건)-[:???]->(무기자차) 관계

승인 후 답변 변화:
  Before: "비건은 클린뷰티, 무기자차는 UV차단" (각각)
  After: "비건과 무기자차는 시너지(lift 1.54), 동시 42% vs 기대 27%" (조합)
```

### 패턴 H: TEMPORAL_CORRELATION (JP sunscreen 비건↑ 톤업↓)

```
PatternScout 절차 Step 4에서 발견됨.
  → compute_temporal_correlation("비건", "톤업", "JP")

데이터 조건:
  비건 월별: [18, 25, 34, 42, 51, 58] % (패턴 A)
  톤업 월별: [67, 61, 55, 50, 46, 43] % (패턴 C)
  pearson correlation ≈ -0.99

  패턴 A+C가 정확히 맞으면 자동 충족. 추가 생성 불필요.
  월별 최소 25건 확인 필요 (180/6 = 30 → 충분).

시드에 없는 것: 비건과 톤업 사이의 역상관 관계

승인 후 답변 변화:
  Before: "톤업 하락은 자연스러운 피부 선호" (추측)
  After: "비건↑과 톤업↓은 역상관(-0.99). 자연주의→인위적 보정 기피" (데이터)
```

### 패턴 I: CROSS_MARKET_GAP (KR vs SG 수분)

```
PatternScout 절차 Step 5에서 발견됨.
  → test_hypothesis("attribute_comparison", {KR수분, SG수분})

데이터 조건:
  KR sunscreen 수분: ~60% (~120건 중 72건)
  SG sunscreen 수분: ~35% (~80건 중 28건)
  chi-squared p < 0.05

시드에 없는 것: SG에서의 수분 수요 잠재성
  (시드에는 SG=열대_다습→피지조절은 있지만, 수분 연결은 약함)
```

### 패턴 J: 열린 발견 — CATEGORY_TRANSFER (보너스)

```
PatternScout 절차에 명시되어 있지 않음.
system prompt의 "위 절차 외에 추가 패턴이 보이면" 조건에 해당.

데이터 조건:
  JP sunscreen 비건 월별: [18, 25, 34, 42, 51, 58] % (급상승)
  JP serum 비건 월별:     [8, 10, 13, 18, 24, 30] % (완만 상승)
  두 시계열 상관: ~0.95+

  JP serum 100건 추가:
    2025-10: ~15건 중 비건 1건 (8%)
    2025-11: ~15건 중 비건 2건 (10%)
    2025-12: ~17건 중 비건 2건 (13%)
    2026-01: ~18건 중 비건 3건 (18%)
    2026-02: ~17건 중 비건 4건 (24%)
    2026-03: ~18건 중 비건 5건 (30%)

발견 여부: 보장 안 됨. PatternScout가 Step 5까지만 하고 끝나면 미발견.
면접 포인트: 발견되면 보너스, 안 되면 구조화된 절차(G,H,I)로 충분.
```

---

## 2. 데이터 생성 요구서 — 다른 에이전트에게 전달

```
=== 데이터 생성 요구서 ===

기존 Doc 1-B (DATA_GENERATION_PROMPT) 기반.
아래 추가 제약을 반영하여 생성.

[제약 1 — 패턴 G]
JP sunscreen 주문에서:
  valueClaims에 "비건" 포함 AND functionalClaims에 "무기자차" 포함인 비율 = 42% (±3%)
  비건 단독: ~58%, 무기자차 단독: ~47%

  검증 SQL:
  SELECT count(*) FILTER (
    WHERE e.attributes->'valueClaims' ? '비건'
      AND e.attributes->'functionalClaims' ? '무기자차'
  )::float / count(*) AS both_rate
  FROM extractions e JOIN orders_unified o ON e.order_id = o.order_id
  WHERE o.destination_country = 'JP' AND e.attributes->>'productType' = 'sunscreen';
  → both_rate ≈ 0.42

[제약 2 — 패턴 I]
KR sunscreen 수분(functionalClaims ? '수분') 비율: 60% (±5%)
SG sunscreen 수분 비율: 35% (±5%)

  검증 SQL:
  SELECT o.destination_country,
    count(*) FILTER (WHERE e.attributes->'functionalClaims' ? '수분')::float
    / count(*) AS moisture_rate
  FROM extractions e JOIN orders_unified o ON e.order_id = o.order_id
  WHERE e.attributes->>'productType' = 'sunscreen'
  GROUP BY 1;
  → KR ≈ 0.60, SG ≈ 0.35

[제약 3 — 패턴 J]
JP serum 100건 생성. 비건 월별 비율:
  2025-10: ~8%, 2025-11: ~10%, 2025-12: ~13%,
  2026-01: ~18%, 2026-02: ~24%, 2026-03: ~30%
월별 최소 15건.

  검증 SQL:
  SELECT DATE_TRUNC('month', o.order_date) AS m,
    count(*) FILTER (WHERE e.attributes->'valueClaims' ? '비건')::float / count(*) AS vegan
  FROM extractions e JOIN orders_unified o ON e.order_id = o.order_id
  WHERE o.destination_country='JP' AND e.attributes->>'productType'='serum'
  GROUP BY 1 ORDER BY 1;

[제약 4 — 기존 패턴 유지]
JP sunscreen 비건 월별: [18, 25, 34, 42, 51, 58] (%)
JP sunscreen 톤업 월별: [67, 61, 55, 50, 46, 43] (%)

[제약 5 — 월별 최소 건수]
모든 국가×카테고리×월 조합 10건+.

  검증 SQL:
  SELECT o.destination_country, e.attributes->>'productType',
    DATE_TRUNC('month', o.order_date), count(*)
  FROM extractions e JOIN orders_unified o ON e.order_id = o.order_id
  GROUP BY 1, 2, 3 HAVING count(*) < 10;
  → 0건이어야 함

=== 끝 ===
```

---

## 3. 5턴 테스트 시나리오

### 턴 1: 비건 트렌드 → PatternScout가 패턴 G 발견

```
사용자: "일본에서 비건 선크림이 왜 상승 중인가?"

AnalystAgent:
  → get_attribute_trend + query_causal_chain → 답변
  → discovered_links: [] (아직 없음)

PatternScout (구조화된 절차):
  Step 1: 주요 속성 = "비건", JP, sunscreen
  Step 2: find_trending_ingredients("JP", "sunscreen", 5)
          → [무기자차(47%), 톤업(43%), 수분(55%), ...]
  Step 3: compute_cooccurrence_lift("비건", "무기자차", "JP", "sunscreen")
          → {lift: 1.54} → propose_relationship(type="SYNERGY") ✅
          compute_cooccurrence_lift("비건", "톤업", ...)
          → {lift: 0.65} → 스킵
  Step 4: compute_temporal_correlation("비건", "톤업", "JP")
          → {correlation: -0.99} → propose_relationship(type="TEMPORAL_CORRELATION") ✅

Eval: 축 1 proposals +2, 축 2 usage 0% (미승인)
```

### 턴 2: 비건+무기자차 질문 (승인 전 — Before 기록)

```
사용자: "일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?"

AnalystAgent:
  → query_causal_chain("JP") → discovered_links: [] (미승인)
  → 답변: "비건은 클린뷰티, 무기자차는 UV차단" (각각 따로)
  ⭐ Before 답변으로 기록

PatternScout:
  Step 5: test_hypothesis("attribute_comparison", {KR수분, SG수분})
  → {p_value: 0.002} → propose_relationship(type="CROSS_MARKET_GAP") ✅

Eval: 축 1 proposals +1 (총 3), 축 2 여전히 0%
```

### [승인 액션] 대시보드에서 SYNERGY + TEMPORAL_CORRELATION 승인

```
POST /api/knowledge/proposals/1/approve (SYNERGY)
POST /api/knowledge/proposals/2/approve (TEMPORAL_CORRELATION)

→ Neo4j:
  (비건)-[:DISCOVERED_LINK {type:"SYNERGY", lift:1.54}]->(무기자차)
  (비건)-[:DISCOVERED_LINK {type:"TEMPORAL_CORRELATION", corr:-0.99}]->(톤업)
```

### 턴 3: 같은 질문 (승인 후 — After 기록) ⭐

```
사용자: "일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?"

AnalystAgent:
  → query_causal_chain("JP") → discovered_links: [{SYNERGY, lift:1.54}] ← 이제 있음!
  → 답변: "비건과 무기자차는 시너지(lift 1.54). 동시 42% vs 기대 27%.
     클린뷰티→자연유래 성분 선호가 동시 수요를 만듦."
  ⭐ After 답변. Before과 명확한 차이.

Eval: 축 2 discovered_usage = 1/3 = 33% ← 점프!
```

### 턴 4: 톤업 질문 (TEMPORAL_CORRELATION 활용)

```
사용자: "일본 선크림에서 톤업이 하락하는 이유는?"

AnalystAgent:
  → query_causal_chain → discovered에 TEMPORAL_CORRELATION 포함
  → 답변: "비건↑과 톤업↓은 역상관(-0.99). 자연주의 트렌드→인위적 보정 기피."

Eval: 축 2 discovered_usage = 2/4 = 50%
```

### 턴 5: 자유 질문 (패턴 J 열린 발견 관찰)

```
사용자: "일본에서 비건 트렌드가 다른 카테고리에도 영향을 주고 있는가?"

AnalystAgent: 답변

PatternScout:
  절차 Step 1~5 실행 후,
  "위 절차 외 추가 패턴" 탐색 시:
  → test_hypothesis("category_transfer", {비건, JP, sunscreen→serum})
  → 발견 시: propose_relationship(type="CATEGORY_TRANSFER") ← 보너스
  → 미발견 시: 구조화된 절차(G,H,I)로 충분
```

---

## 4. 대시보드에서 보이는 최종 상태

```
Knowledge Growth 상단 바 (5턴 후):
  🔍 패턴 탐지: 3~4건 제안 / 2건 승인
  📈 답변 품질: 50% 관계 활용 (0%→33%→50%)
  🧠 추론 커버: 80%
  ⚡ 효율: 비용 추이

상세 보기:
  답변 품질 그래프:
    S1(0%) → S2(0%) → [승인] → S3(33%) → S4(50%)
    ← 승인 시점에 점프

  제안된 관계:
    비건→무기자차 (SYNERGY, lift=1.54) ✅
    비건↔톤업 (TEMPORAL_CORRELATION, r=-0.99) ✅
    수분 KR/SG (CROSS_MARKET_GAP, p=0.002) ⏳
    [sunscreen→serum (CATEGORY_TRANSFER) ⏳ — 발견 시]
```

---

## 5. 검증 체크리스트

```
□ 데이터: 패턴 G(lift≈1.54), H(corr≈-0.99), I(gap≈25%p), J(serum 비건 추이)
□ Phase A: Before 3회 + 스냅샷
□ Phase B: PatternScout 구현 + 5턴 실행
□ 턴 1: PatternScout Step 3에서 SYNERGY 제안됨
□ 턴 1: PatternScout Step 4에서 TEMPORAL_CORRELATION 제안됨
□ 턴 2: Before 답변 기록 (각각 따로 설명)
□ 승인: PROPOSED_LINK → DISCOVERED_LINK 전환
□ 턴 3: After 답변에 lift 수치 포함 (조합 설명) ⭐
□ 턴 4: After 답변에 correlation 수치 포함
□ Eval: discovered_usage_rate 0%→50%
□ 대시보드: 답변 품질 그래프에 승인 시점 점프 보임
```
