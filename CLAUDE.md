# MarketPulse — Project Instructions

## 프로젝트 개요

Cross-Border Ecommerce(역직구) 도메인의 실 주문 데이터 기반 지식 서비스.
뷰티/화장품 업계의 비정형 속성을 구조화하고, 국가별·채널별 인과 체인을 도출하여 사용자에게 인사이트를 제공한다.

## 핵심 도메인 컨텍스트

- **역직구 사업** 특성상 화장품/뷰티 화주·고객사가 대다수
- 뷰티 속성은 **맥락 의존적** — "무기자차"는 선크림에선 UV 차단 타입, 토너에선 무의미
- 키워드/룰 기반 분류 불가 → **LLM few-shot + 벡터 검색** 기반 속성 추출
- 속성 사전 하드코딩 불가 → **자동 확장 루프**로 스키마 진화

## 아키텍처 원칙

### 데이터 레이어
- **Neo4j**: 온톨로지(개념 DB) — Ingredient, Attribute, Country, Trend 등 노드 + 인과 관계
- **PostgreSQL**: 주문 데이터, 속성 트렌드, 히트맵 집계
- 두 DB는 역할이 명확히 분리됨: Neo4j = 지식 그래프, PostgreSQL = 트랜잭션/집계

### 속성 추출 파이프라인
- Golden Example 기반 few-shot learning
- 벡터 검색으로 입력 상품명과 유사한 top-N golden example 선택
- 추출된 속성은 Neo4j 개념 DB에 매핑 (스키마 일관성 강제)
- 미등록 속성 → `additionalAttrs`에 수집 → 빈도 임계치 초과 시 자동 승격

### LLM 도구 제공
- 각 데이터 소스를 **MCP Server**로 래핑하여 LLM이 도구로 호출
  - Neo4j KG Server: 인과 체인 쿼리
  - 주문 데이터 Server: 속성 트렌드, 히트맵 쿼리
- LLM은 사용자 질문에 따라 어떤 도구를 호출할지 자율 판단
- 모든 도구 호출은 `tool_call_traces`에 로깅 (판단 근거 추적)

## 코딩 규칙

### 필수
- 모든 코드 작성 시 **테스트 코드 반드시 작성**
- 구조화된 로깅 사용 (print 금지)
- 비밀값(API 키, 토큰)은 환경변수로 관리, 코드에 하드코딩 금지
- Neo4j Cypher 쿼리는 파라미터 바인딩 사용 (인젝션 방지)
- 타입 힌트 사용

### 금지
- LangChain / LangGraph 사용 금지 — Tool Use 직접 구현
- `SELECT *` 쿼리 금지
- bare except 금지 — 구체적 예외 처리
- 동기 API 호출 금지 — async 우선

### 컨벤션
- Python 3.12+, FastAPI
- 린터: ruff
- 테스트: pytest + pytest-asyncio
- 커밋 메시지: 한글 허용, 변경 이유 중심

## 디렉토리 구조 (계획)

```
src/
├── extraction/        # 속성 추출 파이프라인 (few-shot, golden example)
├── knowledge/         # Neo4j 온톨로지 관리
├── orders/            # PostgreSQL 주문 데이터 접근
├── mcp/               # MCP 서버 (KG, 주문데이터)
├── agents/            # LLM 에이전트 (도구 오케스트레이션)
├── core/              # 공통 인프라 (로깅, 설정, DB 세션)
└── api/               # 사용자 API 엔드포인트
```

## 가정사항

- `orders_unified`에 `product_type`이 이미 존재한다고 가정 (채널 등록 시 카테고리 지정)
- Neo4j 시드 브랜드(4개)와 주문 데이터 브랜드가 일치해야 MADE_BY 100% 매칭

## Learnings

- **Python 3.12 필수**: sentence-transformers, torch, onnxruntime이 3.14 미지원. venv는 반드시 `/usr/local/bin/python3.12 -m venv`로 생성. (ADR-008)
- **numpy < 2 필수**: torch 2.2.2는 numpy 2.x와 비호환. requirements.txt에 `numpy<2` 명시.
- **sentence-transformers < 4.0**: 4.x+ 는 torch 2.4+ 요구, macOS x86_64에서 torch 2.2.2가 최대.
- **chromadb PersistentClient**: `chromadb-client`(HTTP-only)가 아닌 `chromadb`(full) 패키지 사용. Python 3.12에서 정상 동작.
- **Optional 파라미터 명시**: `order=None`처럼 의도적 None은 반드시 명시. 디폴트 의존 금지.
- **프롬프트 파일 분리**: 코드에 인라인하지 않고 `prompts/extractor/v{N}.txt`로 버전 관리.
- **SOLD_IN에 주문량 넣지 않기**: Neo4j=인과, PostgreSQL=집계. 이중 저장 금지. (ADR-007)
