"""LLMOrchestrator 단위 테스트 — Anthropic client mock으로 API 호출 없이 검증.

검증 범위:
  1. ReAct 루프가 tool_use → tool_result → 최종 답변 흐름으로 동작하는지
  2. text block(reasoning)이 steps에 캡처되는지
  3. MAX_STEPS 초과 시 강제 종료되는지
  4. tool_registry에서 도구를 찾아 실행하는지
  5. trace_logger에 기록이 호출되는지
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, call

import pytest

from orchestrator.llm_orchestrator import LLMOrchestrator, OrchestratorResult


# ── Mock 객체 ──


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = "비율 추이를 먼저 확인하겠습니다."


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_001"
    name: str = "get_attribute_trend"
    input: dict = None

    def __post_init__(self):
        if self.input is None:
            self.input = {"attribute_name": "비건", "attribute_type": "value", "countries": ["JP"]}


@dataclass
class MockUsage:
    input_tokens: int = 500
    output_tokens: int = 100


@dataclass
class MockResponse:
    content: list = None
    usage: MockUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = MockUsage()


def make_tool_response(text="분석 중...", tool_name="get_attribute_trend", tool_input=None):
    """도구 호출을 포함한 LLM 응답."""
    return MockResponse(content=[
        MockTextBlock(text=text),
        MockToolUseBlock(name=tool_name, input=tool_input or {"attribute_name": "비건", "attribute_type": "value", "countries": ["JP"]}),
    ])


def make_final_response(text="일본에서 비건이 급상승 중입니다."):
    """최종 답변 (도구 호출 없음)."""
    return MockResponse(content=[MockTextBlock(text=text)])


def make_mock_orchestrator(responses: list[MockResponse]) -> LLMOrchestrator:
    """테스트용 오케스트레이터 생성. LLM 응답을 순서대로 반환."""
    # mock client
    client = MagicMock()
    client.messages.create.side_effect = responses

    # mock servers with @tool 데코레이터 시뮬레이션
    kg_server = MagicMock()
    kg_server.query_causal_chain = MagicMock(return_value=[{"chainStrength": 0.81}])
    kg_server.find_trending_ingredients = MagicMock(return_value=[])
    kg_server.get_product_graph = MagicMock(return_value={})
    kg_server.find_ingredient_synergies = MagicMock(return_value=[])

    order_server = MagicMock()
    order_server.get_attribute_trend = MagicMock(return_value={"trend": {"JP": [{"percentage": 58.0}]}})
    order_server.get_country_attribute_heatmap = MagicMock(return_value={})
    order_server.get_blue_ocean_combinations = MagicMock(return_value={})
    order_server.compare_seller_vs_market = MagicMock(return_value={})

    # mock trace logger
    trace_logger = MagicMock()
    trace_logger.tool_to_server = {}

    # 오케스트레이터 — collect_tool_* 대신 직접 주입
    orch = LLMOrchestrator.__new__(LLMOrchestrator)
    orch.client = client
    orch.model = "claude-sonnet-4-20250514"
    orch.max_steps = 5
    orch.trace_logger = trace_logger
    orch.prompt_template = "테스트 프롬프트"

    orch.tool_registry = {
        "query_causal_chain": kg_server.query_causal_chain,
        "get_attribute_trend": order_server.get_attribute_trend,
        "get_country_attribute_heatmap": order_server.get_country_attribute_heatmap,
    }
    orch._tool_to_server = {
        "query_causal_chain": "kg",
        "get_attribute_trend": "order",
        "get_country_attribute_heatmap": "order",
    }
    orch.tools = []  # mock이므로 빈 리스트

    return orch, kg_server, order_server, trace_logger


# ── 테스트 ──


class TestReActLoop:

    @pytest.mark.asyncio
    async def test_single_tool_then_answer(self):
        """도구 1회 호출 → 최종 답변."""
        orch, _, order, trace = make_mock_orchestrator([
            make_tool_response(text="비율 확인 중"),
            make_final_response(text="비건 58% 상승 중"),
        ])

        result = await orch.ask("일본 비건 트렌드")

        assert result.answer == "비건 58% 상승 중"
        assert result.total_steps == 2
        assert len(result.steps) == 2
        assert result.steps[0]["type"] == "tool_call"
        assert result.steps[1]["type"] == "final_answer"
        order.get_attribute_trend.assert_called_once()

    @pytest.mark.asyncio
    async def test_reasoning_captured_in_steps(self):
        """text block이 steps의 reasoning에 캡처되는지."""
        orch, _, _, _ = make_mock_orchestrator([
            make_tool_response(text="비율 추이부터 확인해야 합니다"),
            make_final_response(text="결론"),
        ])

        result = await orch.ask("테스트")

        assert result.steps[0]["reasoning"] == "비율 추이부터 확인해야 합니다"

    @pytest.mark.asyncio
    async def test_trace_logger_called(self):
        """각 도구 호출 시 trace_logger.log()가 호출되는지."""
        orch, _, _, trace = make_mock_orchestrator([
            make_tool_response(),
            make_final_response(),
        ])

        result = await orch.ask("테스트 질문")

        trace.log.assert_called_once()
        call_kwargs = trace.log.call_args.kwargs
        assert call_kwargs["selected_tool"] == "get_attribute_trend"
        assert call_kwargs["trace_id"] == result.trace_id

    @pytest.mark.asyncio
    async def test_multi_tool_calls(self):
        """도구 2회 호출 → 최종 답변."""
        orch, kg, order, _ = make_mock_orchestrator([
            make_tool_response(text="트렌드 확인"),
            make_tool_response(text="인과 근거 확인", tool_name="query_causal_chain",
                               tool_input={"country_code": "JP"}),
            make_final_response(text="종합 분석 결과"),
        ])

        result = await orch.ask("일본 비건 분석")

        assert result.total_steps == 3
        assert result.steps[0]["tool"] == "get_attribute_trend"
        assert result.steps[1]["tool"] == "query_causal_chain"
        assert result.steps[2]["type"] == "final_answer"

    @pytest.mark.asyncio
    async def test_max_steps_exceeded(self):
        """MAX_STEPS 초과 시 강제 종료."""
        # 5번 모두 도구 호출 → 최종 답변 없이 종료
        orch, _, _, _ = make_mock_orchestrator([
            make_tool_response() for _ in range(6)
        ])
        orch.max_steps = 3

        result = await orch.ask("무한 루프 테스트")

        assert "초과" in result.answer
        assert result.total_steps == 3

    @pytest.mark.asyncio
    async def test_tool_output_summary_in_steps(self):
        """_summarize_output이 steps에 포함되는지."""
        orch, _, _, _ = make_mock_orchestrator([
            make_tool_response(),
            make_final_response(),
        ])

        result = await orch.ask("테스트")

        assert "tool_output_summary" in result.steps[0]

    @pytest.mark.asyncio
    async def test_mcp_server_in_steps(self):
        """steps에 mcp_server가 올바르게 기록되는지."""
        orch, _, _, _ = make_mock_orchestrator([
            make_tool_response(tool_name="get_attribute_trend"),
            make_final_response(),
        ])

        result = await orch.ask("테스트")

        assert result.steps[0]["mcp_server"] == "order"

    @pytest.mark.asyncio
    async def test_cost_calculated(self):
        """total_cost_usd가 계산되는지."""
        orch, _, _, _ = make_mock_orchestrator([
            make_final_response(),
        ])

        result = await orch.ask("간단한 질문")

        assert result.total_cost_usd > 0
        assert result.total_input_tokens == 500
        assert result.total_output_tokens == 100
