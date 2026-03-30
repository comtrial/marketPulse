# MarketPulse — 포트폴리오 설명

## 프로젝트 요약

Cross-Border Ecommerce 도메인에서 실 주문 데이터를 운영 목적 외에 활용할 수 있는 방법을 고민하며 고안한, 뷰티/화장품 상품의 비정형 속성을 구조화하고 국가별 시장 인사이트를 자율 생성하는 LLM 멀티에이전트 시스템입니다. 상품명의 속성이 맥락 의존적이라 룰 기반으로 해결할 수 없는 문제를 정의하고, Tool Use + Dynamic Few-Shot으로 스키마 일관성을 강제하는 추출 파이프라인과, Neo4j 인과 체인 위에서 LLM이 자율적으로 데이터 소스를 조합하는 ReAct 오케스트레이터를 설계·구현했습니다.

---

### | 문제 발굴: 비정형 속성의 맥락 의존성

역직구 뷰티 상품명에서 "무기자차"는 선크림에선 UV 차단 방식이지만 토너에선 무의미하고, "77"이 성분 함량인지 모델 번호인지, "약산성"이 pH 특성인지 마케팅 문구인지는 카테고리에 따라 달라집니다. 이 맥락 의존성 때문에 키워드 매칭이나 룰 기반 분류가 원천적으로 불가능하다는 것을 문제로 정의하고, LLM 기반 접근이 본질적 해결책임을 도출했습니다. 단, LLM만으로는 1,000건 집계 시 키 이름이 제각각이라 GROUP BY가 깨지는 스키마 드리프트 문제가 남아, 이를 해결하기 위해 Tool Use(구조 강제) + Dynamic Few-Shot(값 형식 유도)의 2-레이어 전략을 설계했습니다.

### | 속성 추출 파이프라인: Tool Use + Dynamic Few-Shot

LangChain 없이 Anthropic SDK로 직접 구현하여 파이프라인을 완전히 제어했습니다. ChromaDB + multilingual-e5-large(1024차원) 벡터 검색으로 유사 Gold Example을 찾아 system prompt에 주입하되, 단순 유사도가 아닌 cosine_similarity × 0.7 + attribute_richness × 0.3 가중 정렬로 속성이 풍부한 예시를 우선하여 LLM의 추출 범위를 넓히도록 설계했습니다. 추출 결과는 규칙 기반 검증(errors/warnings 분리)을 거쳐 Neo4j에 graph_sync되며, 검증 통과 시에만 지식 그래프에 반영되는 조건부 적재 구조를 적용했습니다. 프롬프트는 코드에 인라인하지 않고 `prompts/extractor/v{N}.txt`로 파일 분리하여 프롬프트 변경 시 코드 수정 없이 이터레이션할 수 있는 구조를 확보했습니다.

### | 인텔리전스 오케스트레이터: Neo4j("왜?") + PostgreSQL("얼마나?") + LLM("그래서?")

SQL 집계로는 "비건 58%"라는 숫자만 나오고, "왜 58%인가?"에는 답할 수 없습니다. 이를 해결하기 위해 Neo4j에 기후→피부고민→기능→성분의 인과 체인을 온톨로지로 구축하고, LLM이 while-loop ReAct 패턴으로 Neo4j(인과)와 PostgreSQL(집계)을 자율 조합하여 인사이트를 생성하도록 설계했습니다. 8개 MCP 도구의 스키마를 수동으로 300줄 JSON을 쓰는 대신, Pydantic BaseModel + @tool 데코레이터로 `model_json_schema()`에서 자동 생성하여 도구 추가 시 서버 파일 1곳만 수정하면 되는 단일 수정 지점 원칙을 적용했습니다. 모든 도구 호출의 reasoning(사고) + decision(도구 선택) + result(결과)를 tool_call_traces에 기록하여 LLM의 판단 과정을 투명하게 추적할 수 있게 했습니다.

### | PatternScout: 데이터에서 통계적 패턴을 탐지하여 온톨로지 확장

시드 온톨로지가 정적이라는 한계를 해결하기 위해, 주문 데이터에서 통계적 공존 패턴을 자동 탐지하는 별도 에이전트를 설계했습니다. Palantir의 Stage→Review→Approve 패턴을 참고하여, LLM이 "어떤 속성 쌍을 검사할지"만 판단하고 lift·correlation·p-value 계산은 코드(SQL + scipy)가 수행하도록 역할을 분리했습니다. LLM이 생성한 숫자는 재현·검증이 불가능하므로, 통계적 근거는 반드시 코드가 계산하고 evidence로 DB에 저장하여 검증 가능하게 했습니다. 승인된 관계는 Neo4j DISCOVERED_LINK로 편입되어 이후 AnalystAgent 답변에 실제로 반영되며, Before/After 답변 비교에서 "각각 따로 설명"이 "lift=1.55의 시너지 관계"로 변화하는 것을 정량적으로 확인했습니다.

### | 4축 Eval: "답변이 풍부해지고 있다"를 데이터로 보여준다

패턴 탐지 현황, 답변 품질 개선률, 추론 커버리지, 시스템 효율의 4축으로 시스템 성장을 측정하되, 기각한 지표(LLM-as-judge, 답변 길이, evidence density)와 그 이유를 명시적으로 문서화했습니다. 핵심 지표인 discovered_usage_rate(승인된 관계의 답변 활용률)가 Before 0%에서 After 20%로 변화하는 것을 스냅샷으로 정량화하고, 같은 질문의 승인 전/후 답변을 자동으로 찾아 나란히 비교할 수 있는 구조를 구현했습니다.

---

### 주요 구현 내용

- 비정형 상품명에서 맥락 의존적 속성을 구조화하는 Few-Shot + Tool Use 추출 파이프라인 구현
- LLM이 Neo4j(인과) + PostgreSQL(집계) 도구를 자율 조합하는 ReAct 오케스트레이터 구현
- Pydantic @tool 데코레이터로 도구 스키마를 자동 생성하는 구조 설계 (수동 JSON 300줄 제거)
- 통계적 패턴(lift, correlation, p-value)을 코드가 계산하고 LLM이 제안하는 PatternScout 에이전트 구현
- 제안→승인→온톨로지 편입→답변 변화의 Human-in-the-loop 지식 확장 파이프라인 구현
- Neo4j Attribute 노드 동적 생성으로 속성값을 그래프 관계로 승격하는 구조 설계
- 4축 Eval 프레임워크 + Before/After 스냅샷 비교 시스템 구현
- 의사결정 과정을 Think/Act/Observe로 시각화하는 단일 페이지 대시보드 구현
- 19개 Architecture Decision Record로 설계 결정의 맥락·대안·근거를 문서화
- 규칙 기반 검증(errors/warnings 분리), 프롬프트 버전 관리, 원본 키워드 보존 원칙 적용
- 69건 단위 테스트 + 4건 실제 Claude API 통합 테스트

### 기술 스택

Python, FastAPI, Claude API (Sonnet 4 / Tool Use), Neo4j, PostgreSQL, ChromaDB, scipy, Next.js, React, shadcn/ui, Recharts
