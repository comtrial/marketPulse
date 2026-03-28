"""오케스트레이터 실제 Claude API 통합 테스트.

실제 LLM을 호출하여 도구 자동 선택 + 인사이트 생성이 동작하는지 검증.
비용: 테스트당 ~$0.01~0.02, 전체 ~$0.04

실행 조건:
  - Docker: PostgreSQL + Neo4j 기동
  - 데이터: bootstrap_extract 완료 (1,000건 적재)
  - 인덱스: build_index 완료 (50건 벡터 인덱스)
  - .env: ANTHROPIC_API_KEY 설정

실행:
  cd backend && python -m pytest tests/integration/test_orchestrator_live.py -v -s
"""

import pytest
from sqlalchemy import create_engine

from core.config import settings
from core.neo4j_client import neo4j_driver
from mcp_servers.kg_server import KnowledgeGraphServer
from mcp_servers.order_server import OrderDataServer
from orchestrator.llm_orchestrator import LLMOrchestrator
from orchestrator.trace_logger import TraceLogger


@pytest.fixture(scope="module")
def orchestrator():
    """실제 DB + Claude API를 사용하는 오케스트레이터."""
    sync_engine = create_engine(settings.database_url_sync)
    kg_server = KnowledgeGraphServer(driver=neo4j_driver)
    order_server = OrderDataServer(engine=sync_engine)
    trace_logger = TraceLogger(engine=sync_engine, tool_to_server={})

    orch = LLMOrchestrator(
        kg_server=kg_server,
        order_server=order_server,
        trace_logger=trace_logger,
        model=None,  # settings.smart_model 사용
    )
    return orch


@pytest.fixture(scope="module")
def trace_logger():
    sync_engine = create_engine(settings.database_url_sync)
    return TraceLogger(engine=sync_engine, tool_to_server={})


class TestOrchestratorLive:
    """실제 Claude API 호출 테스트. -s 플래그로 출력을 확인."""

    @pytest.mark.asyncio
    async def test_trend_question(self, orchestrator):
        """트렌드 질문 → get_attribute_trend 호출 기대."""
        result = await orchestrator.ask("일본에서 비건 선크림 비율이 어떻게 변하고 있어?")

        print(f"\n=== 트렌드 질문 ===")
        print(f"답변: {result.answer[:200]}...")
        print(f"steps: {result.total_steps}")
        print(f"비용: ${result.total_cost_usd}")
        for step in result.steps:
            if step["type"] == "tool_call":
                print(f"  [{step['step']}] {step['tool']} → {step['tool_output_summary']}")

        # 검증: 도구가 1회 이상 호출됨
        tool_steps = [s for s in result.steps if s["type"] == "tool_call"]
        assert len(tool_steps) >= 1
        # get_attribute_trend가 호출됐어야 함
        tools_used = [s["tool"] for s in tool_steps]
        assert "get_attribute_trend" in tools_used
        # 최종 답변이 비어있지 않음
        assert len(result.answer) > 50
        # trace_id가 존재
        assert result.trace_id

    @pytest.mark.asyncio
    async def test_causal_question(self, orchestrator):
        """인과 질문 → query_causal_chain 호출 기대."""
        result = await orchestrator.ask("일본에서 비건이 왜 인기인지 분석해줘")

        print(f"\n=== 인과 질문 ===")
        print(f"답변: {result.answer[:200]}...")
        print(f"steps: {result.total_steps}")
        print(f"비용: ${result.total_cost_usd}")
        for step in result.steps:
            if step["type"] == "tool_call":
                print(f"  [{step['step']}] {step['tool']} → {step['tool_output_summary']}")

        tool_steps = [s for s in result.steps if s["type"] == "tool_call"]
        assert len(tool_steps) >= 1
        # 인과 체인 도구가 호출됐어야 함
        tools_used = [s["tool"] for s in tool_steps]
        assert "query_causal_chain" in tools_used
        assert len(result.answer) > 50

    @pytest.mark.asyncio
    async def test_ingredient_question(self, orchestrator):
        """성분 질문 → find_ingredient_synergies 또는 find_trending_ingredients 호출 기대."""
        result = await orchestrator.ask("히알루론산과 잘 어울리는 성분이 뭐야?")

        print(f"\n=== 성분 질문 ===")
        print(f"답변: {result.answer[:200]}...")
        print(f"steps: {result.total_steps}")
        print(f"비용: ${result.total_cost_usd}")
        for step in result.steps:
            if step["type"] == "tool_call":
                print(f"  [{step['step']}] {step['tool']} → {step['tool_output_summary']}")

        tool_steps = [s for s in result.steps if s["type"] == "tool_call"]
        assert len(tool_steps) >= 1
        tools_used = [s["tool"] for s in tool_steps]
        assert "find_ingredient_synergies" in tools_used or "find_trending_ingredients" in tools_used
        assert len(result.answer) > 30

    @pytest.mark.asyncio
    async def test_trace_persisted(self, orchestrator, trace_logger):
        """오케스트레이터 호출 후 tool_call_traces에 기록이 남는지."""
        result = await orchestrator.ask("싱가포르 선크림에서 인기 있는 속성이 뭐야?")

        print(f"\n=== Trace 검증 ===")
        print(f"trace_id: {result.trace_id}")

        # DB에서 trace 조회
        traces = trace_logger.get_trace(result.trace_id)
        print(f"DB에 저장된 steps: {len(traces)}건")
        for t in traces:
            print(f"  step {t['step']}: {t['selected_tool']} (mcp: {t['mcp_server']})")

        # tool_call이 있었으면 trace도 있어야 함
        tool_steps = [s for s in result.steps if s["type"] == "tool_call"]
        assert len(traces) >= len(tool_steps)
