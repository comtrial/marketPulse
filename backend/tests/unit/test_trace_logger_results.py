"""TraceLogger 결과 저장/조회 단위 테스트.

orchestrator_results 테이블 연동 검증:
  1. save_result → get_result round-trip
  2. get_result 미존재 시 None 반환
  3. get_recent_results 정렬 검증
  4. steps JSONB에 tool_output이 온전히 저장되는지 (10KB 제한 없음)
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest

from orchestrator.trace_logger import TraceLogger


def make_mock_engine():
    """Mock SQLAlchemy Engine with connection context manager."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return engine, conn


def make_sample_steps():
    """테스트용 steps 데이터."""
    return [
        {
            "step": 1,
            "type": "tool_call",
            "reasoning": "트렌드 확인",
            "tool": "get_attribute_trend",
            "tool_input": {"attribute_name": "비건"},
            "tool_output": {"trend": {"JP": [{"month": "2025-10", "percentage": 19.0}]}},
            "tool_output_summary": "JP: 19.0%→56.0%",
            "mcp_server": "order",
            "latency_ms": 245,
            "success": True,
        },
        {
            "step": 2,
            "type": "final_answer",
            "reasoning": "종합 분석",
            "answer": "비건 트렌드가 상승 중입니다.",
        },
    ]


class TestSaveResult:

    def test_save_result_executes_insert(self):
        """save_result가 INSERT SQL을 실행하는지."""
        engine, conn = make_mock_engine()
        logger = TraceLogger(engine=engine, tool_to_server={})
        steps = make_sample_steps()

        logger.save_result(
            trace_id="test-trace-001",
            user_query="일본 비건 트렌드",
            answer="비건 상승 중",
            steps=steps,
            total_steps=2,
            total_input_tokens=1000,
            total_output_tokens=300,
            total_cost_usd=0.0075,
        )

        conn.execute.assert_called_once()
        conn.commit.assert_called_once()

        # INSERT 쿼리에 올바른 파라미터가 전달되는지
        call_args = conn.execute.call_args
        params = call_args[0][1]
        assert params["trace_id"] == "test-trace-001"
        assert params["query"] == "일본 비건 트렌드"
        assert params["answer"] == "비건 상승 중"
        assert params["total_steps"] == 2
        assert params["in_tok"] == 1000
        assert params["out_tok"] == 300

    def test_save_result_steps_not_truncated(self):
        """steps JSONB에 10KB 제한이 적용되지 않는지 (tool_output 온전 보존)."""
        engine, conn = make_mock_engine()
        logger = TraceLogger(engine=engine, tool_to_server={})

        # 큰 tool_output 생성 (10KB 초과)
        large_output = {"data": "x" * 15000}
        steps = [{
            "step": 1,
            "type": "tool_call",
            "tool": "get_country_attribute_heatmap",
            "tool_output": large_output,
        }]

        logger.save_result(
            trace_id="test-large",
            user_query="히트맵 조회",
            answer="답변",
            steps=steps,
            total_steps=1,
            total_input_tokens=500,
            total_output_tokens=100,
            total_cost_usd=0.003,
        )

        # steps JSON이 잘리지 않았는지 확인
        call_args = conn.execute.call_args
        steps_json = call_args[0][1]["steps"]
        parsed = json.loads(steps_json)
        assert len(parsed[0]["tool_output"]["data"]) == 15000


class TestGetResult:

    def test_get_result_returns_dict(self):
        """존재하는 trace_id에 대해 dict를 반환하는지."""
        engine, conn = make_mock_engine()
        logger = TraceLogger(engine=engine, tool_to_server={})

        # Mock DB row
        mock_row = MagicMock()
        mock_row._mapping = {
            "trace_id": "abc-123",
            "user_query": "테스트 질문",
            "answer": "답변 텍스트",
            "steps": make_sample_steps(),
            "total_steps": 2,
            "total_input_tokens": 1000,
            "total_output_tokens": 300,
            "total_cost_usd": 0.0075,
            "created_at": "2026-03-28T12:00:00",
        }
        conn.execute.return_value.fetchone.return_value = mock_row

        result = logger.get_result("abc-123")

        assert result is not None
        assert result["trace_id"] == "abc-123"
        assert result["answer"] == "답변 텍스트"
        assert len(result["steps"]) == 2
        assert result["total_input_tokens"] == 1000
        assert result["total_output_tokens"] == 300

    def test_get_result_returns_none_for_missing(self):
        """존재하지 않는 trace_id에 대해 None 반환."""
        engine, conn = make_mock_engine()
        logger = TraceLogger(engine=engine, tool_to_server={})
        conn.execute.return_value.fetchone.return_value = None

        result = logger.get_result("nonexistent")

        assert result is None


class TestGetRecentResults:

    def test_get_recent_results_returns_list(self):
        """최근 결과 목록이 올바른 형태로 반환되는지."""
        engine, conn = make_mock_engine()
        logger = TraceLogger(engine=engine, tool_to_server={})

        mock_rows = []
        for i in range(3):
            row = MagicMock()
            row._mapping = {
                "trace_id": f"trace-{i}",
                "user_query": f"질문 {i}",
                "total_steps": 2 + i,
                "total_cost_usd": 0.01 * (i + 1),
                "created_at": f"2026-03-28T{12 + i}:00:00",
            }
            mock_rows.append(row)
        conn.execute.return_value = mock_rows

        results = logger.get_recent_results(limit=10)

        assert len(results) == 3
        assert results[0]["trace_id"] == "trace-0"
        assert results[0]["total_cost_usd"] == 0.01
