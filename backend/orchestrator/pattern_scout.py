"""PatternScout — 구조화된 절차로 통계적 패턴을 탐지하는 에이전트.

AnalystAgent와 분리됨 (ADR-016):
  AnalystAgent: 사용자 질문에 답하기 (읽기 도구만)
  PatternScout: 통계적 패턴 탐지 (읽기 + 쓰기 도구)

트리거: 매 AnalystAgent 턴 완료 후 자동 실행 (ADR-009 MVP).
도구: 13개 (Data 8 + Logic 3 + Action 2).
MAX_STEPS: 7 (구조화된 5단계 절차 + 여유 2).

통계 검증은 코드가 수행 (ADR-017).
LLM은 "어떤 속성 쌍을 검사할지"만 판단.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import anthropic
import structlog

from core.config import settings
from orchestrator.tool_decorator import collect_tool_registry, collect_tool_schemas
from orchestrator.trace_logger import TraceLogger

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "pattern_scout"


@dataclass
class PatternScoutResult:
    trace_id: str
    total_steps: int
    proposals_made: int = 0


class PatternScout:
    """구조화된 절차로 통계적 패턴을 탐지하는 에이전트."""

    MAX_STEPS = 7

    def __init__(
        self,
        kg_server,
        order_server,
        logic_server,
        action_server,
        trace_logger: TraceLogger,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        prompt_version: str = "v1",
    ):
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.smart_model
        self.trace_logger = trace_logger
        self.prompt_template = self._load_prompt(prompt_version)

        # 4개 서버에서 도구 스키마 + 레지스트리 자동 수집
        self.tool_registry: dict[str, callable] = {}
        self._tool_to_server: dict[str, str] = {}
        self.tools: list[dict] = []

        self._register_server("kg", kg_server)
        self._register_server("order", order_server)
        self._register_server("logic", logic_server)
        self._register_server("action", action_server)

        logger.info(
            "pattern_scout_initialized",
            model=self.model,
            tools=list(self.tool_registry.keys()),
        )

    def _register_server(self, server_name: str, server_instance) -> None:
        schemas = collect_tool_schemas(server_instance)
        registry = collect_tool_registry(server_instance)
        self.tools.extend(schemas)
        self.tool_registry.update(registry)
        for name in registry:
            self._tool_to_server[name] = server_name

    @staticmethod
    def _load_prompt(version: str) -> str:
        path = PROMPTS_DIR / f"{version}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def run_discovery(
        self,
        analyst_trace_id: str,
        analyst_query: str,
    ) -> PatternScoutResult:
        """직전 AnalystAgent 분석 맥락에서 패턴 탐색 실행.

        Args:
            analyst_trace_id: 직전 AnalystAgent의 trace_id (맥락 전달)
            analyst_query: 직전 질문 (어떤 속성/국가/카테고리인지 파악)

        Returns:
            PatternScoutResult with trace_id, steps, proposals count
        """
        trace_id = f"scout-{uuid4()}"

        # 직전 분석 맥락을 user message로 전달
        prompt = (
            f"직전 분석 질문: {analyst_query}\n"
            f"이 맥락에서 탐색 절차를 실행하세요."
        )

        messages = [{"role": "user", "content": prompt}]
        step = 0
        proposals_made = 0

        while step < self.MAX_STEPS:
            step += 1

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.prompt_template,
                tools=self.tools,
                messages=messages,
            )

            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            current_reasoning = "\n".join(b.text for b in text_blocks) if text_blocks else ""

            if not tool_blocks:
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for tb in tool_blocks:
                tool_name = tb.name
                tool_input = tb.input

                start_ms = time.time()
                try:
                    tool_fn = self.tool_registry[tool_name]
                    tool_output = tool_fn(tool_input)
                    success = True
                    error_msg = None
                except Exception as e:
                    tool_output = {"error": str(e)}
                    success = False
                    error_msg = str(e)
                    logger.error("scout_tool_failed", tool=tool_name, error=str(e))
                latency_ms = (time.time() - start_ms) * 1000

                # trace 로깅 — agent_type="pattern_scout"
                self.trace_logger.log(
                    trace_id=trace_id,
                    step=step,
                    user_query=analyst_query,
                    selected_tool=tool_name,
                    tool_input=tool_input,
                    selection_reason=current_reasoning,
                    tool_output=tool_output,
                    tool_latency_ms=latency_ms,
                    tool_success=success,
                    error_message=error_msg,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    agent_type="pattern_scout",
                )

                # 제안 카운트
                if tool_name == "propose_relationship" and success:
                    if isinstance(tool_output, dict) and tool_output.get("status") == "proposed":
                        proposals_made += 1

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(tool_output, ensure_ascii=False, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        logger.info(
            "pattern_scout_complete",
            trace_id=trace_id,
            analyst_query=analyst_query[:50],
            total_steps=step,
            proposals_made=proposals_made,
        )

        return PatternScoutResult(
            trace_id=trace_id,
            total_steps=step,
            proposals_made=proposals_made,
        )
