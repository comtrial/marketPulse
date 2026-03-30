# MarketPulse 시스템 흐름 가이드 — 코드 레벨 시나리오 매핑

> 실제 시나리오 "일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?"을 따라가며,
> 코드가 어떤 순서로 실행되고, 어떤 데이터가 어디에 저장되는지를 추적한다.

---

## 시나리오 전체 흐름 요약

```
사용자가 프리셋 클릭
    │
    ▼
[Phase A] AnalystAgent — 사용자 질문에 답하기
    │  벡터 검색 없음 (속성 추출이 아닌 인텔리전스 질의)
    │  ReAct while-loop: LLM이 도구 자율 선택
    │  → query_causal_chain → get_attribute_trend × 2
    │  → 최종 답변 생성
    │
    ▼
[Phase B] PatternScout — 통계적 패턴 탐지
    │  구조화된 5단계 절차
    │  → find_trending_ingredients → compute_cooccurrence_lift
    │  → propose_relationship (lift > 1.3이면)
    │
    ▼
[Phase C] 사람이 대시보드에서 승인
    │  PROPOSED_LINK → DISCOVERED_LINK 전환
    │
    ▼
[Phase D] 같은 질문 재실행 → 답변이 달라짐
    │  query_causal_chain이 DISCOVERED_LINK 포함 반환
    │  → LLM이 lift=1.55를 인용하여 답변
```

---

## Phase A: AnalystAgent 실행

### A-1. 사용자가 프리셋 클릭

```
프론트엔드: frontend/src/components/query-panel.tsx
  → PresetItem 클릭
  → onSubmit("일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?")
  → page.tsx::handleSubmit()
  → api.ask(query) → POST /api/v1/orchestrator/ask
```

### A-2. FastAPI → LLMOrchestrator.ask()

```
api/routes_orchestrator.py::ask()
  → orchestrator.ask(user_query=req.query)

orchestrator/llm_orchestrator.py::ask()
  trace_id = str(uuid4())  # 예: "994002c2-..."
  messages = [{"role": "user", "content": "일본 선크림에서..."}]

  while step < MAX_STEPS(5):
```

### A-3. Step 1 — LLM이 query_causal_chain 선택

```
LLM 호출:
  client.messages.create(
    model="claude-sonnet-4-20250514",
    system=prompts/orchestrator/v1.txt,     ← 도구 선택 규칙
    tools=self.tools,                        ← 8개 도구 스키마 (Pydantic 자동 생성)
    messages=[{user: "일본 선크림에서..."}]
  )

LLM 응답:
  [TextBlock("인과 체인과 트렌드를 확인하겠습니다"),
   ToolUseBlock(name="query_causal_chain", input={"country_code": "JP"})]
        ↑ reasoning                              ↑ decision

코드 실행:
  tool_fn = self.tool_registry["query_causal_chain"]  ← collect_tool_registry()로 자동 수집된 함수
  tool_output = tool_fn({"country_code": "JP"})       ← @tool 데코레이터가 dict→Pydantic 변환

실제 실행되는 곳:
  mcp_servers/kg_server.py::query_causal_chain()
    │
    ├─ Cypher 1: MATCH (Country)-[:HAS_CLIMATE]->(ClimateZone)-[:TRIGGERS]->(SkinConcern)...
    │  → seed_chains = [{climate:"온대_고UV여름", skinConcern:"자외선손상",
    │                     triggerStrength:0.88, function:"UV차단", demandStrength:0.92, chainStrength:0.81}, ...]
    │
    ├─ Cypher 2: MATCH (a)-[r:DISCOVERED_LINK]->(b)
    │  → discovered_links = []  ← 아직 승인 전이므로 0건
    │
    └─ return {"seed_chains": [...3건...], "discovered_links": []}

로깅:
  trace_logger.log(
    trace_id="994002c2-...",
    step=1,
    selected_tool="query_causal_chain",
    tool_input={"country_code": "JP"},
    tool_output={"seed_chains": [...], "discovered_links": []},
    selection_reason="인과 체인과 트렌드를 확인하겠습니다",
    agent_type="analyst",                                        ← agent_type 구분
    mcp_server="kg",                                             ← _tool_to_server 매핑
  )
  → INSERT INTO tool_call_traces (trace_id, step, ..., agent_type, mcp_server)
```

### A-4. Step 2-3 — get_attribute_trend × 2

```
LLM: "비건과 무기자차 각각의 추이를 확인하겠습니다"
  → get_attribute_trend(attribute_name="비건", attribute_type="value", countries=["JP"])
  → get_attribute_trend(attribute_name="무기자차", attribute_type="additional", countries=["JP"])

실행되는 곳:
  mcp_servers/order_server.py::get_attribute_trend()
    │
    ├─ "value" 타입: SQL → e.attributes->'valueClaims' @> CAST(:attr_json AS jsonb)
    │  → {trend: {JP: [{month:"2025-10", percentage:17.5}, ..., {month:"2026-03", percentage:58.7}]}}
    │
    └─ "additional" 타입: _get_additional_attr_trend()
       → jsonb_each_text(e.attributes->'additionalAttrs') WHERE kv.v = '무기자차'
       → {trend: {JP: [{month:"2025-10", percentage:47.5}, ...]}}
```

### A-5. Step 4 — 최종 답변 생성

```
LLM: tool_use 없이 텍스트만 응답
  → "비건은 클린뷰티 트렌드(17.5%→58.7%), 무기자차는 UV차단 효과(47%)..."
  → discovered_links=[] 이므로 lift 수치 없음 ← Before 답변

코드:
  final_text = current_reasoning  # LLM의 텍스트 블록
  all_steps.append({"step": 4, "type": "final_answer", "answer": final_text})
  break  # while-loop 종료
```

### A-6. 결과 저장

```
orchestrator/llm_orchestrator.py:
  OrchestratorResult(
    answer="비건은 클린뷰티...",
    trace_id="994002c2-...",
    steps=[{step:1, tool:"query_causal_chain", ...},
           {step:2, tool:"get_attribute_trend", ...},
           {step:3, tool:"get_attribute_trend", ...},
           {step:4, type:"final_answer", ...}],
    total_cost_usd=0.088,
  )

  trace_logger.save_result(
    trace_id="994002c2-...",
    user_query="일본 선크림에서...",
    answer="비건은 클린뷰티...",
    steps=[...],                    ← 전체 steps JSONB, 잘림 없음
  )
  → INSERT INTO orchestrator_results (trace_id, user_query, answer, steps, ...)
```

---

## Phase B: PatternScout 자동 실행

### B-1. AnalystAgent 완료 후 자동 트리거

```
orchestrator/llm_orchestrator.py::ask() 끝부분:
  if self.pattern_scout is not None:
    scout_result = self.pattern_scout.run_discovery(
      analyst_trace_id="994002c2-...",
      analyst_query="일본 선크림에서 비건과 무기자차를..."
    )
    result.scout_trace_id = scout_result.trace_id
    result.scout_proposals = scout_result.proposals_made
```

### B-2. PatternScout system prompt 주입

```
orchestrator/pattern_scout.py::run_discovery():
  trace_id = str(uuid4())  # 예: "e8526c4f-..."

  prompt = "직전 분석 질문: 일본 선크림에서 비건과 무기자차를...\n이 맥락에서 탐색 절차를 실행하세요."

  system_prompt = prompts/pattern_scout/v1.txt
  ↓
  "Step 1: 직전 분석의 주요 속성을 파악하세요.
   Step 2: 조합 후보를 가져오세요.
   Step 3: compute_cooccurrence_lift... lift > 1.3이면 propose_relationship
   Step 4: compute_temporal_correlation... |corr| > 0.6이면 propose_relationship
   Step 5: test_hypothesis... p < 0.05이면 propose_relationship"
```

### B-3. Step 1-2 — 후보 속성 조회

```
PatternScout LLM:
  "주요 속성 = 비건, 국가 = JP, 카테고리 = sunscreen"
  → find_trending_ingredients(country_code="JP", product_type="sunscreen", top_k=5)

실행되는 곳:
  mcp_servers/kg_server.py::find_trending_ingredients()
  → Cypher: Product-[:SOLD_IN]->Country(JP), Product-[:IS_TYPE]->ProductType(sunscreen),
            Product-[:CONTAINS]->Ingredient
  → [{ingredient:"징크옥사이드", productCount:125}]

로깅: agent_type="pattern_scout", mcp_server="kg"
```

### B-4. Step 3 — lift 계산 + 제안

```
PatternScout LLM:
  "비건과 무기자차의 동시 출현을 검사하겠습니다"
  → compute_cooccurrence_lift(attr_a="비건", attr_b="무기자차", country="JP", product_type="sunscreen")

실행되는 곳:
  mcp_servers/logic_server.py::compute_cooccurrence_lift()
    │
    ├─ SQL: WITH base AS (SELECT ... WHERE country='JP' AND productType='선크림')
    │       COUNT(*) FILTER (WHERE valueClaims @> '["비건"]' AND additionalAttrs에 '무기자차')
    │  → total=264, has_a=101, has_b=125, has_both=74
    │
    ├─ Python 계산:
    │  rate_a = 101/264 = 0.383
    │  rate_b = 125/264 = 0.473
    │  rate_both = 74/264 = 0.280
    │  expected = 0.383 × 0.473 = 0.181
    │  lift = 0.280 / 0.181 = 1.55  ← 코드가 계산한 수치
    │
    └─ return {lift: 1.55, evidence_strength: "moderate", sample_size: 264}

PatternScout LLM: "lift=1.55 > 1.3 임계치. 제안하겠습니다"
  → propose_relationship(
      source_concept="비건",
      target_concept="무기자차",
      relationship_type="SYNERGY",
      evidence={"lift": 1.55, "rate_both": 0.28, "sample_size": 264, ...},
      reasoning="비건과 무기자차의 동시 출현이 독립 기대치보다 55% 높음..."
    )

실행되는 곳:
  mcp_servers/action_server.py::propose_relationship()
    │
    ├─ 중복 체크: SELECT id FROM relationship_proposals WHERE source='비건' AND target='무기자차'
    │  → 없음
    │
    ├─ PG INSERT:
    │  INSERT INTO relationship_proposals (source_concept, target_concept, relationship_type,
    │    evidence, reasoning, status) VALUES ('비건', '무기자차', 'SYNERGY',
    │    '{"lift":1.55,...}', '비건과 무기자차의...', 'proposed')
    │  → RETURNING id = 2
    │
    └─ Neo4j:
       MERGE (s:Attribute {name: '비건'})      ← Attribute 노드 동적 생성
       MERGE (t:Attribute {name: '무기자차'})
       MERGE (s)-[r:PROPOSED_LINK {proposalId: 2}]->(t)
       SET r.type = 'SYNERGY', r.evidence = '{"lift":1.55,...}'

로깅: agent_type="pattern_scout", mcp_server="action"
```

### B-5. PatternScout 완료

```
PatternScoutResult(
  trace_id="e8526c4f-...",
  total_steps=7,
  proposals_made=1,
)
```

### B-6. 프론트엔드로 응답 반환

```
api/routes_orchestrator.py::ask()
  → AskResponse(
      answer="비건은 클린뷰티...",           ← AnalystAgent 답변
      trace_id="994002c2-...",
      scout_trace_id="e8526c4f-...",         ← PatternScout trace
      scout_proposals=1,                      ← 제안 1건
      steps=[...],
      total_cost_usd=0.088,
    )

프론트엔드:
  Zone B: AnalystAgent 답변 시각화 (차트 + 인과 + Markdown)
  Zone C: AnalystAgent trace (Step 1~4)
  Knowledge Growth 바: "1건 제안"
```

---

## Phase C: 사람이 대시보드에서 승인

### C-1. 대시보드 proposals 테이블

```
프론트엔드: frontend/src/components/knowledge-growth.tsx
  → GET /api/v1/knowledge/proposals
  → [{id:2, source_concept:"비건", target_concept:"무기자차",
      relationship_type:"SYNERGY", evidence:{lift:1.55,...}, status:"proposed"}]

  테이블 렌더링:
    타입: SYNERGY
    소스 → 타겟: 비건 → 무기자차
    근거: lift=1.55
    상태: proposed
    [✅ 승인] [❌ 거부]
```

### C-2. [승인] 클릭

```
프론트엔드: api.approveProposal(2) → POST /api/v1/knowledge/proposals/2/approve

api/routes_eval.py::approve_proposal(proposal_id=2):
  │
  ├─ PG: UPDATE relationship_proposals SET status='approved', approved_at=NOW() WHERE id=2
  │
  └─ Neo4j:
     ① MATCH ()-[r:PROPOSED_LINK {proposalId: 2}]->() DELETE r
        → PROPOSED_LINK 삭제 (제안 상태 제거)

     ② MERGE (s:Attribute {name: '비건'})
        MERGE (t:Attribute {name: '무기자차'})
        MERGE (s)-[new:DISCOVERED_LINK {proposalId: 2}]->(t)
        SET new.type = 'SYNERGY',
            new.evidence = '{"lift":1.55,...}',
            new.source = 'pattern_scout'
        → DISCOVERED_LINK 생성 (승인 상태)
```

---

## Phase D: 같은 질문 재실행 → 답변이 달라짐

### D-1. 사용자가 같은 프리셋 클릭

```
POST /api/v1/orchestrator/ask
  {query: "일본 선크림에서 비건과 무기자차를 함께 가진 상품이 많은 이유는?"}
```

### D-2. AnalystAgent Step 1 — query_causal_chain (이번에는 DISCOVERED_LINK 포함)

```
mcp_servers/kg_server.py::query_causal_chain(country_code="JP"):
  │
  ├─ Cypher 1 (시드): 기존과 동일
  │  → seed_chains = [{chainStrength:0.81, ...}, ...]
  │
  ├─ Cypher 2 (발견된 관계): MATCH (a)-[r:DISCOVERED_LINK]->(b)
  │  → discovered_links = [{
  │      fromConcept: "비건",
  │      toConcept: "무기자차",
  │      relationType: "SYNERGY",
  │      evidence: '{"lift":1.55,"rate_both":0.28,"sample_size":264,...}'
  │    }]                                                               ← 이번에는 1건!
  │
  └─ return {
       "seed_chains": [...3건...],
       "discovered_links": [...1건...]    ← Before에서는 [] 이었음
     }
```

### D-3. LLM이 DISCOVERED_LINK의 lift 수치를 인용

```
LLM이 받은 tool_result:
  {"seed_chains": [...], "discovered_links": [{"relationType":"SYNERGY","evidence":"{"lift":1.55,...}"}]}

LLM 최종 답변:
  "비건과 무기자차는 **1.55배의 리프트 스코어**를 보이며 실제 시너지가 있음
   동시 출현율: 28.0% (예상 18.1%보다 훨씬 높음)"
                  ↑ evidence에서 인용한 코드 계산 수치
```

### D-4. Eval이 이 변화를 측정

```
eval/metrics.py::eval_answer_quality():
  orchestrator_results.steps를 순회
  → query_causal_chain의 tool_output에서 discovered_links 체크
  → Before(64cfd44d): discovered_links=[] → used=False
  → After(e4062df9): discovered_links=[{...}] → used=True
  → discovered_usage_rate = 1/5 = 0.20 (20%)

eval/metrics.py::find_before_after_pairs():
  같은 user_query가 2회 이상:
    Before(64cfd44d): discovered 없음
    After(e4062df9): discovered 있음
  → pair 반환: {before_answer: "비건은 클린뷰티...", after_answer: "lift=1.55 시너지..."}
```

---

## 데이터 저장 위치 요약

```
                          PostgreSQL                         Neo4j
                    ┌─────────────────────┐         ┌──────────────────────┐
Phase A 결과:       │ orchestrator_results │         │                      │
                    │   trace_id           │         │                      │
                    │   answer (Before)    │         │                      │
                    │   steps (JSONB)      │         │                      │
                    │                     │         │                      │
Phase A trace:      │ tool_call_traces    │         │                      │
                    │   agent_type=analyst│         │                      │
                    │   each step logged  │         │                      │
                    ├─────────────────────┤         │                      │
Phase B 결과:       │ relationship_proposals│        │ (:Attribute {비건})   │
                    │   id=2, status=proposed│      │   -[:PROPOSED_LINK]→  │
                    │   evidence={lift:1.55}│       │ (:Attribute {무기자차})│
                    │                     │         │                      │
Phase B trace:      │ tool_call_traces    │         │                      │
                    │   agent_type=        │         │                      │
                    │     pattern_scout   │         │                      │
                    ├─────────────────────┤         ├──────────────────────┤
Phase C 승인:       │ status→'approved'   │         │ PROPOSED_LINK 삭제    │
                    │ approved_at=NOW()   │         │ DISCOVERED_LINK 생성  │
                    │                     │         │   type=SYNERGY        │
                    │                     │         │   evidence={lift:1.55}│
                    ├─────────────────────┤         ├──────────────────────┤
Phase D 결과:       │ orchestrator_results │         │ query_causal_chain이  │
                    │   answer (After)    │         │ DISCOVERED_LINK 반환  │
                    │   steps에            │         │                      │
                    │   discovered_links  │         │                      │
                    │   포함됨             │         │                      │
                    ├─────────────────────┤         │                      │
Eval 측정:          │ eval/snapshots/     │         │                      │
                    │   before_*.json     │         │                      │
                    │   after_*.json      │         │                      │
                    └─────────────────────┘         └──────────────────────┘
```

---

## 파일 실행 순서 매핑

```
사용자 클릭
  → frontend/src/app/page.tsx::handleSubmit()
  → frontend/src/lib/api.ts::api.ask()
  → POST /api/v1/orchestrator/ask

  → backend/api/routes_orchestrator.py::ask()
  → backend/orchestrator/llm_orchestrator.py::ask()
    │
    ├─ Anthropic API 호출 (Claude Sonnet 4)
    ├─ tool_use 파싱
    ├─ tool_registry에서 함수 찾기 (orchestrator/tool_decorator.py::collect_tool_registry)
    │
    ├─ [도구 실행] backend/mcp_servers/kg_server.py::query_causal_chain()
    │     └─ Neo4j Cypher 실행 (core/neo4j_client.py::neo4j_driver)
    │
    ├─ [도구 실행] backend/mcp_servers/order_server.py::get_attribute_trend()
    │     └─ PostgreSQL 쿼리 실행 (sqlalchemy engine)
    │
    ├─ [로깅] backend/orchestrator/trace_logger.py::log()
    │     └─ INSERT INTO tool_call_traces
    │
    ├─ [저장] backend/orchestrator/trace_logger.py::save_result()
    │     └─ INSERT INTO orchestrator_results
    │
    └─ [PatternScout] backend/orchestrator/pattern_scout.py::run_discovery()
        │
        ├─ Anthropic API 호출 (같은 모델)
        ├─ [도구] backend/mcp_servers/logic_server.py::compute_cooccurrence_lift()
        │     └─ PostgreSQL SQL 집계 + Python 계산
        ├─ [도구] backend/mcp_servers/action_server.py::propose_relationship()
        │     ├─ PostgreSQL INSERT (relationship_proposals)
        │     └─ Neo4j MERGE (Attribute + PROPOSED_LINK)
        └─ [로깅] trace_logger.log(agent_type="pattern_scout")

승인 클릭
  → frontend: api.approveProposal(id)
  → POST /api/v1/knowledge/proposals/{id}/approve

  → backend/api/routes_eval.py::approve_proposal()
    ├─ PostgreSQL: status='approved'
    ├─ Neo4j: DELETE PROPOSED_LINK
    └─ Neo4j: MERGE DISCOVERED_LINK

재실행
  → 같은 흐름, 하지만 query_causal_chain이 discovered_links=[{...}]를 반환
  → LLM이 lift=1.55를 인용하여 답변 생성
```
