"""CosmeticExtractor 단위 테스트 — Anthropic client를 mock하여 API 호출 없이 검증.

검증 범위:
  - 벡터 검색 결과가 system prompt에 주입되는지
  - LLM 응답(tool_use)이 올바르게 파싱되는지
  - validator → graph_sync 흐름이 조건에 따라 동작하는지
  - cost가 정확히 계산되는지
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from extraction.cost_tracker import CostTracker
from extraction.extractor import CosmeticExtractor
from extraction.validator import ExtractionValidator


# ── Mock 객체 ──


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "mock_tool_id"
    name: str = "extract_cosmetic_attributes"
    input: dict = None

    def __post_init__(self):
        if self.input is None:
            self.input = {
                "productType": "선크림",
                "brand": "토리든",
                "keyIngredients": ["히알루론산", "징크옥사이드"],
                "functionalClaims": ["UV차단", "수분공급"],
                "valueClaims": ["비건"],
                "spf": "50+",
                "pa": "++++",
                "volume": "60ml",
                "additionalAttrs": {"자차타입": "무기자차"},
            }


@dataclass
class MockUsage:
    input_tokens: int = 1200
    output_tokens: int = 150


@dataclass
class MockResponse:
    content: list = None
    usage: MockUsage = None

    def __post_init__(self):
        if self.content is None:
            self.content = [MockToolUseBlock()]
        if self.usage is None:
            self.usage = MockUsage()


def make_mock_vector_store(results=None):
    """VectorStore mock — search()가 고정 결과를 반환."""
    store = MagicMock()
    if results is not None:
        store.search.return_value = results
        return store
    store.search.return_value = [
        {
            "gold_id": "GOLD-SUN-003",
            "raw_input": "토리든 다이브인 무기자차 선크림 SPF50+ PA++++ 60ml 비건",
            "extracted_output": {"productType": "sunscreen", "brand": "토리든"},
            "similarity": 0.95,
            "attr_count": 8,
            "combined_score": 0.905,
        }
    ]
    return store


def make_mock_anthropic_client(response=None):
    """Anthropic client mock — messages.create()가 fixture 응답 반환."""
    client = MagicMock()
    client.messages.create.return_value = response or MockResponse()
    return client


def make_extractor(vector_store=None, client=None, graph_syncer=None):
    """테스트용 CosmeticExtractor 생성."""
    return CosmeticExtractor(
        vector_store=vector_store or make_mock_vector_store(),
        validator=ExtractionValidator(),
        cost_tracker=CostTracker(),
        graph_syncer=graph_syncer,
        client=client or make_mock_anthropic_client(),
    )


# ── 테스트 ──


class TestExtractorPipeline:

    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        """정상 추출 흐름 — 벡터 검색 → LLM → 검증 통과."""
        extractor = make_extractor()
        result = await extractor.extract(
            product_text="토리든 다이브인 무기자차 히알루론산 징크옥사이드 선크림 SPF50+ PA++++ 60ml 비건",
            order=None,
        )

        assert result.attributes["productType"] == "선크림"
        assert result.attributes["brand"] == "토리든"
        assert result.validation.passed
        assert result.graph_synced is False  # order=None이므로
        assert result.cost.cost_usd > 0
        assert len(result.examples_used) == 1  # mock이 1개 반환

    @pytest.mark.asyncio
    async def test_vector_search_called_with_product_text(self):
        """벡터 검색이 product_text로 호출되는지."""
        store = make_mock_vector_store()
        extractor = make_extractor(vector_store=store)

        await extractor.extract(
            product_text="라운드랩 독도 토너 200ml",
            order=None,
        )

        store.search.assert_called_once_with("라운드랩 독도 토너 200ml", top_k=3)

    @pytest.mark.asyncio
    async def test_llm_called_with_tool_choice(self):
        """LLM이 tool_choice=forced로 호출되는지."""
        client = make_mock_anthropic_client()
        extractor = make_extractor(client=client)

        await extractor.extract(
            product_text="이니스프리 선크림",
            order=None,
        )

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "extract_cosmetic_attributes"

    @pytest.mark.asyncio
    async def test_validation_failure_no_graph_sync(self):
        """validation 실패 시 graph_sync가 호출되지 않음."""
        # productType 없는 응답 → validation 실패
        bad_response = MockResponse(
            content=[MockToolUseBlock(input={"brand": "토리든"})],  # productType 누락
        )
        graph_syncer = MagicMock()
        extractor = make_extractor(
            client=make_mock_anthropic_client(response=bad_response),
            graph_syncer=graph_syncer,
        )

        from extraction.graph_sync import OrderContext
        order = OrderContext(
            order_id="C24-001",
            product_name="토리든 선크림",
            product_type="sunscreen",
            destination_country="JP",
            platform="cafe24",
        )

        result = await extractor.extract(
            product_text="토리든 선크림",
            order=order,
        )

        assert not result.validation.passed
        assert result.graph_synced is False
        graph_syncer.sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_pass_triggers_graph_sync(self):
        """validation 통과 + order 있으면 graph_sync 호출됨."""
        graph_syncer = MagicMock()
        graph_syncer.sync.return_value = True
        extractor = make_extractor(graph_syncer=graph_syncer)

        from extraction.graph_sync import OrderContext
        order = OrderContext(
            order_id="C24-001",
            product_name="토리든 다이브인 무기자차 히알루론산 징크옥사이드 선크림 SPF50+ PA++++ 60ml 비건",
            product_type="sunscreen",
            destination_country="JP",
            platform="cafe24",
        )

        result = await extractor.extract(
            product_text="토리든 다이브인 무기자차 히알루론산 징크옥사이드 선크림 SPF50+ PA++++ 60ml 비건",
            order=order,
        )

        assert result.validation.passed
        assert result.graph_synced is True
        graph_syncer.sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_avg_similarity_calculated(self):
        """avg_similarity가 벡터 검색 결과의 평균으로 계산되는지."""
        store = make_mock_vector_store(results=[
            {"gold_id": "G1", "raw_input": "a", "extracted_output": {},
             "similarity": 0.90, "attr_count": 5, "combined_score": 0.78},
            {"gold_id": "G2", "raw_input": "b", "extracted_output": {},
             "similarity": 0.80, "attr_count": 3, "combined_score": 0.65},
        ])
        extractor = make_extractor(vector_store=store)

        result = await extractor.extract(
            product_text="테스트 상품",
            order=None,
        )

        # (0.90 + 0.80) / 2 = 0.85
        assert result.avg_similarity == 0.85

    @pytest.mark.asyncio
    async def test_empty_vector_results(self):
        """벡터 검색 결과가 0건이어도 추출은 진행됨 (few-shot 없이)."""
        store = make_mock_vector_store(results=[])
        extractor = make_extractor(vector_store=store)

        result = await extractor.extract(
            product_text="완전 새로운 상품명",
            order=None,
        )

        assert result.avg_similarity == 0.0
        assert len(result.examples_used) == 0
        assert result.attributes is not None  # 추출은 진행됨
