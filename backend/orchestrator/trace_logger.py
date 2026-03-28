"""LLM 의사결정 흐름 로깅 — 프론트엔드 시각화 대비.

각 step이 캡처하는 것:
  reasoning    — LLM의 사고 과정 ("상승이 확인됐으므로 인과 체인을 확인해야...")
  decision     — 어떤 도구를 선택했는가 ("query_causal_chain")
  tool_input   — 어떤 파라미터로 호출했는가
  tool_output  — 도구가 반환한 결과

프론트엔드가 그릴 수 있는 흐름도:
  [질문] → [사고1] → [도구A] → [결과A] → [사고2] → [도구B] → [결과B] → [최종 답변]

왜 필요한가:
  1. 디버깅 — LLM이 왜 이 도구를 선택했는지 추적
  2. 패턴 분석 — 어떤 질문 유형에 어떤 도구가 자주 쓰이는지
  3. 비용 최적화 — 도구별 레이턴시/비용 분석
"""

import json
from dataclasses import dataclass, field

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = structlog.get_logger()


@dataclass
class TraceStep:
    """단일 step의 구조화된 데이터. 프론트엔드 렌더링용."""

    step: int
    type: str  # "tool_call" | "final_answer"
    reasoning: str  # LLM의 사고 과정 (text block)
    tool: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None
    tool_output_summary: str | None = None  # 핵심 수치 요약 (시각화용)
    mcp_server: str | None = None  # "kg" | "order"
    latency_ms: float | None = None
    answer: str | None = None  # final_answer일 때만


@dataclass
class TraceFlow:
    """전체 trace의 구조화된 흐름. GET /api/v1/orchestrator/trace/{id} 응답."""

    trace_id: str
    query: str
    total_steps: int
    total_cost_usd: float
    steps: list[TraceStep] = field(default_factory=list)


class TraceLogger:
    """tool_call_traces 테이블에 판단 흐름을 기록하고 조회한다.

    tool_to_server 매핑은 외부에서 주입받는다 — 도구가 추가/제거될 때
    trace_logger를 수정할 필요 없이 오케스트레이터에서 매핑만 갱신하면 됨.
    """

    def __init__(self, engine: Engine, tool_to_server: dict[str, str]):
        """
        Args:
            engine: SQLAlchemy sync engine
            tool_to_server: 도구 이름 → MCP 서버 이름 매핑
                            (예: {"query_causal_chain": "kg", "get_attribute_trend": "order"})
                            오케스트레이터가 서버별 도구를 등록할 때 자동 생성.
        """
        self.engine = engine
        self.tool_to_server = tool_to_server

    def _resolve_server(self, tool_name: str) -> str:
        """도구 이름으로 소속 MCP 서버를 찾는다. 매핑에 없으면 "unknown"."""
        return self.tool_to_server.get(tool_name, "unknown")

    def log(
        self,
        trace_id: str,
        step: int,
        user_query: str,
        selected_tool: str,
        tool_input: dict,
        selection_reason: str,
        tool_output: dict | None = None,
        tool_latency_ms: float = 0,
        tool_success: bool = True,
        error_message: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """단일 도구 호출 step을 tool_call_traces에 기록."""
        mcp_server = self._resolve_server(selected_tool)
        cost_usd = input_tokens * 3 / 1_000_000 + output_tokens * 15 / 1_000_000

        # tool_output이 너무 크면 잘라서 저장 (10KB 제한)
        output_str = json.dumps(tool_output, ensure_ascii=False, default=str)
        if len(output_str) > 10000:
            output_str = output_str[:10000]

        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO tool_call_traces
                        (trace_id, step, user_query, selected_tool,
                         tool_input, selection_reason, tool_output,
                         tool_latency_ms, tool_success, error_message,
                         input_tokens, output_tokens, cost_usd, mcp_server)
                    VALUES
                        (:trace_id, :step, :query, :tool,
                         :input, :reason, :output::jsonb,
                         :latency, :success, :error,
                         :in_tok, :out_tok, :cost, :mcp)
                """),
                {
                    "trace_id": trace_id,
                    "step": step,
                    "query": user_query,
                    "tool": selected_tool,
                    "input": json.dumps(tool_input, ensure_ascii=False),
                    "reason": selection_reason,
                    "output": output_str,
                    "latency": round(tool_latency_ms),
                    "success": tool_success,
                    "error": error_message,
                    "in_tok": input_tokens,
                    "out_tok": output_tokens,
                    "cost": round(cost_usd, 6),
                    "mcp": mcp_server,
                },
            )
            conn.commit()

    def get_trace(self, trace_id: str) -> list[dict]:
        """특정 trace_id의 전체 step을 조회. 프론트엔드 시각화용."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT trace_id, step, user_query, selected_tool,
                           tool_input, selection_reason, tool_output,
                           tool_latency_ms, tool_success, error_message,
                           input_tokens, output_tokens, cost_usd, mcp_server,
                           timestamp
                    FROM tool_call_traces
                    WHERE trace_id = :tid
                    ORDER BY step ASC
                """),
                {"tid": trace_id},
            )
            return [dict(row._mapping) for row in result]

    def get_recent_traces(self, limit: int = 20) -> list[dict]:
        """최근 trace 목록 (요약). trace별 도구 사용 현황."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT trace_id,
                           user_query,
                           MAX(step) AS total_steps,
                           array_agg(selected_tool ORDER BY step) AS tools_used,
                           SUM(cost_usd) AS total_cost,
                           MAX(timestamp) AS last_step_at
                    FROM tool_call_traces
                    GROUP BY trace_id, user_query
                    ORDER BY MAX(timestamp) DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            )
            return [dict(row._mapping) for row in result]
