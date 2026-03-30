"""핵심 속성 추출 로직 — 파이프라인의 중심.

전체 흐름 (LLM 호출 1회):
  상품명 → 벡터 검색(top-3) → LLM(Tool Use + Few-Shot) → 검증 → 적재 + graph_sync

2-레이어 전략:
  Tool Use  → 구조 강제 (키 이름, 타입). "functionalClaims"이 항상 string[]로 나오는 것을 보장.
  Few-Shot  → 값 형식 유도. "어성초 추출물"이 아닌 "어성초"로 쓰도록 유도.

왜 LLM 1회만 호출하는가:
  - 카테고리 사전 분류 제거 (ADR-002): 벡터 검색이 암묵적으로 해결
  - Multi-Turn 자기 검증 제거 (ADR-003): 규칙 기반 검증으로 대체
  - Confidence 모듈 제거 (ADR-005): validator errors 유무로 판단

graph_sync 조건:
  validation.passed=True (errors 없음) → graph_sync 수행
  validation.passed=False (errors 있음) → DB 적재만, graph_sync 안 함

프롬프트 관리:
  prompts/extractor/v{N}.txt — 버전별 파일로 관리
  코드에서 인라인하지 않음 → 프롬프트 변경 시 코드 수정 불필요
"""

import json
import time
import uuid
from pathlib import Path

import anthropic
import structlog

from core.config import settings
from extraction.cost_tracker import CostTracker
from extraction.graph_sync import GraphSynchronizer, OrderContext
from extraction.schemas import ExtractionResult, ExtractionTrace
from extraction.tool_schema import EXTRACTION_TOOL
from extraction.validator import ExtractionValidator
from extraction.vector_store import VectorStore

logger = structlog.get_logger()

# 프롬프트 파일 기본 경로
PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "extractor"


class CosmeticExtractor:
    """K-뷰티 화장품 속성 추출기.

    Args:
        vector_store: gold example 검색 (few-shot 소스)
        validator: 규칙 기반 검증 (errors/warnings)
        cost_tracker: 토큰/비용 추적
        graph_syncer: Neo4j 동기화 (optional, 없으면 skip)
        client: Anthropic API 클라이언트
        model: 사용할 Claude 모델 (기본: settings.smart_model)
                haiku로 교체하면 비용 절감, sonnet이면 정확도 우선
        prompt_version: 프롬프트 버전 (기본: "v1")
    """

    def __init__(
        self,
        vector_store: VectorStore,
        validator: ExtractionValidator,
        cost_tracker: CostTracker,
        graph_syncer: GraphSynchronizer | None = None,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        prompt_version: str = "v1",
    ):
        self.vector_store = vector_store
        self.validator = validator
        self.cost_tracker = cost_tracker
        self.graph_syncer = graph_syncer
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.smart_model
        self.prompt_template = self._load_prompt(prompt_version)

        logger.info(
            "extractor_initialized",
            model=self.model,
            prompt_version=prompt_version,
        )

    @staticmethod
    def _load_prompt(version: str) -> str:
        """프롬프트 파일을 로드.

        prompts/extractor/v1.txt, v2.txt, ... 형태로 버전 관리.
        프롬프트 변경 시 코드 수정 없이 파일만 추가/수정하면 됨.
        """
        path = PROMPTS_DIR / f"{version}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    async def extract(
        self,
        product_text: str,
        order: OrderContext | None = None,
    ) -> ExtractionResult:
        """상품명에서 구조화된 속성을 추출.

        Args:
            product_text: 원본 상품명 (예: "토리든 다이브인 무기자차 선크림 SPF50+ PA++++ 60ml 비건")
            order: 주문 컨텍스트 (graph_sync에 필요, 없으면 graph_sync skip)

        Returns:
            ExtractionResult with attributes, validation, cost, graph_synced
        """
        extraction_id = str(uuid.uuid4())

        # ① 벡터 검색 — 유사한 gold example top-3
        examples = self.vector_store.search(product_text, top_k=3)
        avg_similarity = (
            sum(e["similarity"] for e in examples) / len(examples)
            if examples
            else 0.0
        )

        logger.info(
            "few_shot_examples_found",
            extraction_id=extraction_id,
            count=len(examples),
            avg_similarity=round(avg_similarity, 3),
            gold_ids=[e["gold_id"] for e in examples],
        )

        # ② 프롬프트 구성 — gold example을 system prompt에 주입
        system_prompt = self._build_system_prompt(examples)

        # ③ LLM 호출 — model 파라미터로 받은 모델 사용, Tool Use 강제 (1회)
        start_time = time.time()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_cosmetic_attributes"},
            messages=[
                {
                    "role": "user",
                    "content": f"다음 K-뷰티 상품의 속성을 추출하세요:\n\n{product_text}",
                }
            ],
        )
        latency_ms = (time.time() - start_time) * 1000

        # ④ 결과 파싱 — tool_use 블록에서 속성 추출
        tool_block = next(b for b in response.content if b.type == "tool_use")
        raw_attrs = tool_block.input

        # ⑤ 규칙 기반 검증 — errors/warnings 분리
        validation = self.validator.validate(raw_attrs, product_text)

        # ⑥ 비용 계산
        cost = self.cost_tracker.calculate(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        # ⑦ graph_sync — errors가 없고, order 컨텍스트가 있을 때만
        graph_synced = False
        if order and validation.passed and self.graph_syncer:
            try:
                graph_synced = self.graph_syncer.sync(order, raw_attrs)
            except Exception as e:
                logger.error(
                    "graph_sync_failed",
                    extraction_id=extraction_id,
                    error=str(e),
                )

        logger.info(
            "extraction_complete",
            extraction_id=extraction_id,
            model=self.model,
            product_type=raw_attrs.get("productType"),
            brand=raw_attrs.get("brand"),
            validation_passed=validation.passed,
            errors=len(validation.errors),
            warnings=len(validation.warnings),
            graph_synced=graph_synced,
            cost_usd=cost.cost_usd,
            latency_ms=cost.latency_ms,
        )

        # ⑧ 트레이스 데이터 — 프론트엔드 Zone C에서 각 단계 상세를 펼쳐볼 수 있도록
        trace = ExtractionTrace(
            vector_search=[
                {
                    "gold_id": e["gold_id"],
                    "raw_input": e["raw_input"],
                    "similarity": round(e["similarity"], 4),
                    "combined_score": round(e.get("combined_score", e["similarity"]), 4),
                    "extracted_output": e["extracted_output"],
                }
                for e in examples
            ],
            few_shot_prompt=self._build_example_block(examples),
            llm_response={
                "model": self.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            validation_details={
                "passed": validation.passed,
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
        )

        return ExtractionResult(
            attributes=raw_attrs,
            validation=validation,
            examples_used=[e["gold_id"] for e in examples],
            avg_similarity=round(avg_similarity, 3),
            cost=cost,
            graph_synced=graph_synced,
            trace=trace,
        )

    @staticmethod
    def _build_example_block(examples: list[dict]) -> str:
        """검색된 gold example을 few-shot 블록 문자열로 포맷."""
        block = ""
        for i, ex in enumerate(examples, 1):
            block += (
                f"\n예시 {i} (유사도: {ex['similarity']:.2f}):\n"
                f"  상품명: {ex['raw_input']}\n"
                f"  추출 결과: {json.dumps(ex['extracted_output'], ensure_ascii=False)}\n"
            )
        return block

    def _build_system_prompt(self, examples: list[dict]) -> str:
        """프롬프트 템플릿에 벡터 검색 결과 gold example을 주입."""
        return self.prompt_template.replace("{examples}", self._build_example_block(examples))
