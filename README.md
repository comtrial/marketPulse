# MarketPulse

Cross-Border Ecommerce 실 주문 데이터 기반의 뷰티/화장품 지식 서비스.

비정형 상품명에서 맥락 의존적 속성을 추출하고, Neo4j 인과 체인으로 연결하여
국가별·채널별 인사이트를 제공한다.

---

## 왜 이 프로젝트가 필요한가

역직구 사업의 실 주문 데이터가 그저 운영에만 쓰이는 것이 아깝다. 뷰티 업계 특성상 속성이 비정형적이고 맥락 의존적이라("무기자차"는 선크림에선 UV 차단 방식이지만 토너에선 무의미), 룰 기반이나 키워드 기반으로는 해결할 수 없다.

LLM(zero-shot)도 개별 추출은 가능하지만, 1,000건 집계 시 키 이름이 제각각("주요성분" vs "key_ingredient")이라 GROUP BY가 안 된다. **Dynamic Few-Shot의 진짜 가치는 개별 정확도 향상이 아니라, 대규모 집계를 위한 스키마 일관성 강제다.**

---

## 아키텍처

```
상품명 입력
    │
    ▼
[벡터 검색] ChromaDB — 유사 gold example top-3
    │  intfloat/multilingual-e5-large (1024차원)
    │  정렬: 유사도×0.7 + 속성풍부도×0.3
    │
    ▼
[LLM 추출] Claude Sonnet 4 + Tool Use + Few-Shot (1회 호출)
    │  Tool Use → 구조 강제 (키 이름, 타입)
    │  Few-Shot → 값 형식 유도 ("어성초 추출물" → "어성초")
    │
    ▼
[규칙 기반 검증] LLM 호출 없음
    │  errors: 타입, 범위, 필수필드 → graph_sync 차단
    │  warnings: 환각 의심, 교차 의심 → 통과하되 로그
    │
    ▼
[적재]
    ├─ PostgreSQL: extractions 테이블 (항상)
    └─ Neo4j: Product 노드 + 관계 (validation 통과 시)
```

### 데이터 소스 역할 분리

| DB | 역할 | 답하는 질문 |
|----|------|-----------|
| **Neo4j** | 온톨로지 + 인과 체인 | "왜?" — 기후→피부고민→기능→성분→상품 |
| **PostgreSQL** | 주문 데이터 + 집계 | "얼마나?" — 비율, 주문량, 시계열 |
| **ChromaDB** | 벡터 검색 | "비슷한 사례?" — few-shot example 검색 |

### Neo4j 지식 그래프

```
[추상 계층 — 시드]
  Country →HAS_CLIMATE→ ClimateZone →TRIGGERS→ SkinConcern
    →DRIVES_DEMAND→ Function ←HAS_FUNCTION← Ingredient

[물리적 데이터 — graph_sync가 동적 생성]
  Product →CONTAINS→ Ingredient
  Product →SOLD_IN→ Country    ← 주문 데이터에서
  Product →SOLD_ON→ Platform   ← 주문 데이터에서
  Product →MADE_BY→ Brand      ← LLM 추출 결과에서
  Product →IS_TYPE→ ProductType ← 주문 데이터에서
```

---

## 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| Runtime | Python | 3.12 |
| Web | FastAPI | 0.115+ |
| RDB | PostgreSQL | 16 |
| Graph DB | Neo4j Community | 5.26 |
| Vector DB | ChromaDB (PersistentClient) | 1.5+ |
| Embedding | intfloat/multilingual-e5-large | 1024차원 |
| LLM | Claude Sonnet 4 (Anthropic) | Tool Use |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migration | Alembic | 1.14+ |
| Logging | structlog | 25+ |
| Test | pytest + pytest-asyncio | 9.0+ |
| Lint | ruff | 0.8+ |
| Frontend | Next.js (App Router) | 16 |
| UI | React + shadcn/ui + Tailwind CSS | 19 |
| Chart | Recharts | 3.8+ |
| Markdown | react-markdown + remark-gfm | 10+ |

**의도적으로 사용하지 않은 것**: LangChain, LangGraph — Tool Use를 직접 구현하여 파이프라인을 완전히 제어.

---

## 디렉토리 구조

```
backend/
├── api/                    # FastAPI 라우터
│   ├── routes_health.py    #   GET  /api/v1/health
│   ├── routes_extract.py   #   POST /api/v1/extract, /extract/batch, GET /extract/stats
│   └── routes_orchestrator.py  POST /ask, GET /result/{id}, GET /results, GET /traces
├── orchestrator/               # LLM 오케스트레이터
│   ├── llm_orchestrator.py     #   ReAct while-loop + OrchestratorResult
│   ├── tool_decorator.py       #   @tool + Pydantic→Anthropic 스키마 자동 생성
│   └── trace_logger.py         #   판단 흐름 로깅 + 결과 영속화
├── mcp_servers/                # MCP 도구 서버 (8개 도구)
│   ├── kg_server.py            #   Neo4j 4도구: causal_chain, trending, synergies, product
│   └── order_server.py         #   PostgreSQL 4도구: trend, heatmap, blue_ocean, compare
├── core/                   # 인프라
│   ├── config.py           #   Pydantic Settings (env vars)
│   ├── database.py         #   SQLAlchemy async 엔진
│   ├── neo4j_client.py     #   Neo4j 드라이버
│   └── logging.py          #   structlog 설정
├── extraction/             # 속성 추출 파이프라인 (핵심)
│   ├── tool_schema.py      #   Claude Tool Use 스키마 정의
│   ├── vector_store.py     #   ChromaDB + e5-large 벡터 검색
│   ├── extractor.py        #   파이프라인 오케스트레이터 (LLM 1회 호출)
│   ├── validator.py        #   규칙 기반 검증 (errors/warnings)
│   ├── cost_tracker.py     #   토큰/비용 추적
│   ├── graph_sync.py       #   Neo4j 동기화 (Product → 온톨로지 연결)
│   └── schemas.py          #   데이터 클래스
├── models/
│   ├── db_models.py        #   SQLAlchemy ORM (7 테이블)
│   └── schemas.py          #   API Pydantic 모델
├── prompts/
│   └── extractor/v1.txt    #   추출 프롬프트 (버전 관리)
├── data/                   # 시드 + 스크립트
│   ├── seed_neo4j.py       #   Neo4j 온톨로지 시드 (39노드, 34관계)
│   ├── seed_db.py          #   PostgreSQL 시드 (gold + orders)
│   ├── build_index.py      #   ChromaDB 벡터 인덱스 빌드
│   ├── bootstrap_extract.py#   규칙 기반 부트스트랩 (LLM 비용 $0)
│   └── generate_orders.py  #   주문 데이터 생성 (패턴 A-F)
├── tests/
│   └── unit/               #   단위 테스트 57건
├── alembic/                #   DB 마이그레이션
├── main.py                 #   FastAPI 앱 팩토리
└── docker-compose.yml      #   PostgreSQL + Neo4j

frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx            # 3존 대시보드 레이아웃
│   │   └── globals.css         # Tailwind + 애니메이션
│   ├── components/
│   │   ├── query-panel.tsx     # Zone A — 질문 패널 (프리셋 + 직접 입력)
│   │   ├── result-panel.tsx    # Zone B — 시각화 결과 (차트, 히트맵, 인과 플로우)
│   │   ├── trace-panel.tsx     # Zone C — ReAct 트레이스 (Think/Act/Observe)
│   │   ├── visualizations.tsx  # 5종 시각화 컴포넌트 + determineVisualizations()
│   │   ├── bottom-bar.tsx      # 시스템 상태 바
│   │   └── ui/                 # shadcn/ui 컴포넌트 (Card, ScrollArea, Markdown...)
│   └── lib/
│       └── api.ts              # API 클라이언트 + 타입 정의
└── package.json                # Next.js 16 + Recharts + react-markdown
```

---

## 실행 방법

### 사전 조건

- Python 3.12, Docker, Docker Compose

### 1. 환경 설정

```bash
cp .env.example .env
# .env에서 ANTHROPIC_API_KEY 설정
```

### 2. 인프라 기동

```bash
docker compose up -d postgres neo4j
```

### 3. Python 환경

```bash
/usr/local/bin/python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. DB 마이그레이션 + 시드

```bash
cd backend
alembic upgrade head                    # PostgreSQL 테이블 생성
python -m data.seed_neo4j               # Neo4j 온톨로지 (39노드, 34관계)
python -m data.seed_db                  # Gold 50건 + 주문 1,000건
python -m data.build_index              # ChromaDB 벡터 인덱스
python -m data.bootstrap_extract --clean # 규칙 기반 부트스트랩 (1,000건)
```

### 5. 서버 실행

```bash
uvicorn main:create_app --factory --port 8000
```

### 6. 프론트엔드

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### 7. API 테스트

```bash
# 인텔리전스 질의 (LLM 자동 도구 선택)
curl -X POST http://localhost:8000/api/v1/orchestrator/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "일본에서 비건 선크림이 왜 상승 중인지 분석해줘"}'

# 이전 결과 재조회 (LLM 재호출 없음)
curl http://localhost:8000/api/v1/orchestrator/result/{trace_id}

# 최근 분석 이력
curl http://localhost:8000/api/v1/orchestrator/results

# 단건 추출 (LLM 호출)
curl -X POST http://localhost:8000/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"product_name": "토리든 다이브인 무기자차 선크림 SPF50+ PA++++ 60ml 비건"}'

# 추출 통계
curl http://localhost:8000/api/v1/extract/stats

# 헬스체크
curl http://localhost:8000/api/v1/health
```

### 8. 테스트

```bash
cd backend
pytest tests/unit/ -v    # 단위 테스트 57건
```

---

## 데이터 현황

| 항목 | 수량 |
|------|------|
| Gold Examples | 50건 (5유형 × 10건) |
| 주문 데이터 | 1,000건 (Cafe24 495 + Qoo10 342 + Shopee 163) |
| Neo4j 온톨로지 | 39노드, 34관계 (시드) |
| Neo4j Product | 1,000노드 (부트스트랩) |
| Neo4j 관계 총합 | IS_TYPE 1,000 + SOLD_IN 1,000 + SOLD_ON 1,000 + MADE_BY 1,000 + CONTAINS 724 |
| Extractions | 1,000건 (validation 100% 통과) |
| 단위 테스트 | 57건 |
| 통합 테스트 | 4건 (실제 Claude API) |

### 주문 데이터 패턴 (generate_orders.py)

| 패턴 | 설명 | 검증 가능한 인사이트 |
|------|------|---------------------|
| A | JP 선크림 "비건" 비율 상승 (18%→58%) | 시계열 트렌드 |
| B | SG 선크림 "워터프루프" 안정 (72-78%) | 국가별 속성 특성 |
| C | JP 선크림 "톤업" 하락 (67%→43%) | 레드오션 감지 |
| D | JP "비건+무기자차" 블루오션 (1상품, 고반복) | 블루오션 파인더 |
| E | "마이크로바이옴" 신규 속성 등장 (0→25건) | 신규 속성 감지 |
| F | 국가별 성분 선호도 차이 | 국가별 히트맵 |

---

## 대시보드

3존 레이아웃 단일 페이지 대시보드. 질문 선택 → LLM이 도구 자동 선택 → 시각화 결과 + 사고 과정 동시 표시.

```
┌──────────────────────────────────────────┬──────────────────────┐
│  Zone A — 질문 패널 (프리셋 + 직접 입력)  │                      │
├──────────────────────────────────────────┤  Zone C              │
│                                          │  Decision Trace      │
│  Zone B — 시각화 결과                     │                      │
│  ┌─ LineChart ─────────────────────┐     │  STEP 1 ● PostgreSQL │
│  │ JP: 19% → 56% (비건)           │     │  ┌ Think ──────────┐ │
│  └─────────────────────────────────┘     │  │ 비율 추이 확인.. │ │
│  ┌─ CausalChain ───────────────────┐     │  ├ Act ────────────┤ │
│  │ UV기후 →(0.92) UV손상 →(0.88)   │     │  │ get_attr_trend  │ │
│  └─────────────────────────────────┘     │  ├ Observe ────────┤ │
│  ┌─ LLM 분석 (Markdown) ──────────┐     │  │ JP: 19%→56%     │ │
│  │ ## 분석 결과                    │     │  └─────────────────┘ │
│  │ 일본에서 비건 선크림이...        │     │  █████████░░ 1,203ms │
│  └─────────────────────────────────┘     │                      │
├──────────────────────────────────────────┴──────────────────────┤
│  시스템 상태 바 — 추출 1,000건 | 비용 $4.20 | Neo4j 1,039노드    │
└────────────────────────────────────────────────────────────────┘
```

### Zone B — 도구별 시각화

| MCP 도구 | 시각화 | 데이터 소스 |
|----------|--------|-----------|
| `get_attribute_trend` | Recharts LineChart (국가별 월별 곡선) | PostgreSQL |
| `get_country_attribute_heatmap` | 색상 그리드 히트맵 (국가×속성) | PostgreSQL |
| `query_causal_chain` | 인과 플로우 (기후→피부고민→기능) | Neo4j |
| `find_trending_ingredients` | 수평 BarChart (성분별 상품 수) | Neo4j |
| `find_ingredient_synergies` | 뱃지 리스트 (도메인지식/동시출현) | Neo4j |
| 최종 답변 | Markdown 렌더링 | Claude LLM |

### Zone C — ReAct 트레이스

LLM의 사고 과정을 Think(amber) → Act(서버 색상) → Observe(sky) 3단계로 시각화.
타임라인 UI, latency 워터폴 바, 토큰 사용량 그리드, 서버 분포 stacked bar 포함.

### 결과 재조회

한 번 질의한 결과는 `orchestrator_results` 테이블에 자동 저장되어, LLM 재호출 없이 `GET /result/{trace_id}`로 동일 결과를 재조회할 수 있다.

---

## 핵심 설계 결정 (ADR)

자세한 내용은 [docs/adr/](docs/adr/) 참조.

| ADR | 결정 | 핵심 근거 |
|-----|------|----------|
| 001 | Neo4j 온톨로지 | SQL 집계로는 인과 체인 도출 불가 |
| 002 | Golden Example few-shot | 스키마 일관성 + flywheel 확장성 |
| 003 | 자동 속성 승격 루프 | 사람 손 최소화, 트렌드 자동 반영 |
| 004 | MCP Server 데이터 노출 | LLM 자율 도구 선택 + 추적성 |
| 005 | Tool Use + Few-Shot 2레이어 | 구조 강제 + 값 형식 유도 분리 |
| 006 | Confidence 모듈 제거 | MVP에서 운영 시나리오 없음, validator suffient |
| 007 | SOLD_IN 단순화 | Neo4j=왜, PostgreSQL=얼마나 역할 분리 |
| 008 | Python 3.12 고정 | sentence-transformers/torch 호환성 |
| 009 | 도구-서버 매핑 주입 | 하드코딩 대신 오케스트레이터가 매핑 자동 생성 후 주입 |
| 010 | Pydantic 도구 스키마 자동 생성 | 수동 300줄 JSON 대신 BaseModel→model_json_schema() 자동 생성 |
| 011 | 원본 키워드 보존 원칙 | 추출 시 동의어 변환 금지, 집계 단계에서 매핑 — 정보 손실 방지 |
| 012 | 오케스트레이터 결과 영속화 | orchestrator_results 테이블로 전체 결과 저장 — 재조회 시 LLM 재호출 없이 동일 결과 |
| 013 | Zone B 도구 결과 시각화 | determineVisualizations() 패턴으로 도구별 차트 자동 매핑 |
| 014 | Zone C ReAct Think/Act/Observe UI | LangSmith/Langfuse 패턴 참고 — 타임라인, 워터폴, 토큰 그리드 |
