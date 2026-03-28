"""while-loop ReAct 패턴의 LLM 오케스트레이터.

Anthropic SDK 직접 사용. LangChain/LangGraph 없음.

작동 흐름:
  1. 사용자 질문 + 사용 가능한 도구 목록(8개)을 LLM에 전달
  2. LLM이 tool_use 블록으로 응답 → 해당 도구 실행 → 결과를 tool_result로 주입
  3. LLM이 텍스트만으로 응답 → 최종 답변
  4. 각 step의 reasoning(text block) + decision(tool_use block)을 trace에 기록
  5. MAX_STEPS 초과 시 강제 종료

도구 스키마 관리:
  collect_tool_schemas() — 서버의 @tool 데코레이터에서 Anthropic Tool 스키마 자동 수집
  collect_tool_registry() — 서버의 @tool 데코레이터에서 이름→함수 매핑 자동 수집
  수동으로 300줄짜리 스키마를 쓰지 않음 — Pydantic BaseModel이 단일 진실 소스.

판단 흐름 시각화:
  각 step에서 text block(reasoning)과 tool_use block(decision)을 분리 캡처하여
  프론트엔드가 의사결정 흐름도를 렌더링할 수 있게 한다.
  [질문] → [사고1] → [도구A] → [결과] → [사고2] → [도구B] → [결과] → [답변]
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import anthropic
import structlog

from core.config import settings
from mcp_servers.kg_server import KnowledgeGraphServer
from mcp_servers.order_server import OrderDataServer
from orchestrator.tool_decorator import collect_tool_registry, collect_tool_schemas
from orchestrator.trace_logger import TraceLogger

logger = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "orchestrator"


@dataclass
class OrchestratorResult:
    """오케스트레이터 실행 결과. API 응답 + 프론트엔드 시각화용."""

    answer: str
    trace_id: str
    steps: list[dict] = field(default_factory=list)
    total_steps: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


class LLMOrchestrator:
    """while-loop ReAct 패턴으로 MCP 도구를 자동 선택·호출한다.

    도구 스키마와 레지스트리는 서버의 @tool 데코레이터에서 자동 수집.
    tool_to_server 매핑도 서버별 등록 시 자동 생성 → TraceLogger에 주입.
    """

    def __init__(
        self,
        kg_server: KnowledgeGraphServer,
        order_server: OrderDataServer,
        trace_logger: TraceLogger,
        client: anthropic.Anthropic | None = None,
        model: str | None = None,
        prompt_version: str = "v1",
        max_steps: int = 5,
    ):
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.smart_model
        self.max_steps = max_steps
        self.trace_logger = trace_logger
        self.prompt_template = self._load_prompt(prompt_version)

        # @tool 데코레이터에서 스키마 + 레지스트리 자동 수집
        # 수동으로 도구 정의를 쓰지 않음 — Pydantic 모델이 단일 진실 소스
        self.tool_registry: dict[str, callable] = {}
        self._tool_to_server: dict[str, str] = {}
        self.tools: list[dict] = []

        self._register_server("kg", kg_server)
        self._register_server("order", order_server)

        # tool_to_server 매핑을 trace_logger에 주입 (ADR-009)
        self.trace_logger.tool_to_server = self._tool_to_server

        logger.info(
            "orchestrator_initialized",
            model=self.model,
            tools=list(self.tool_registry.keys()),
            prompt_version=prompt_version,
        )

    def _register_server(self, server_name: str, server_instance: object) -> None:
        """서버의 @tool 메서드를 자동 수집하여 레지스트리에 등록.

        collect_tool_schemas() — Anthropic Tool 형식 스키마 수집
        collect_tool_registry() — 이름→함수 매핑 수집
        서버별 tool_to_server 매핑도 자동 생성.
        """
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

    async def ask(self, user_query: str) -> OrchestratorResult:
        """사용자 질문에 대해 도구를 자동 선택·호출하고 최종 답변을 생성.

        ReAct 루프:
          1. LLM에 질문 + 도구 목록 전달
          2. LLM이 text(사고) + tool_use(결정)로 응답
          3. 도구 실행 → 결과를 tool_result로 주입
          4. 반복 (최대 max_steps)
          5. LLM이 텍스트만 응답하면 종료
        """
        trace_id = str(uuid4())
        messages = [{"role": "user", "content": user_query}]
        all_steps: list[dict] = []
        total_input = 0
        total_output = 0
        step = 0
        final_text = ""

        while step < self.max_steps:
            step += 1

            # ── LLM 호출 ──
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.prompt_template,
                tools=self.tools,
                messages=messages,
            )

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            # ── text block(사고) + tool_use block(결정) 분리 캡처 ──
            text_blocks = [b for b in response.content if b.type == "text"]
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            current_reasoning = "\n".join(b.text for b in text_blocks) if text_blocks else ""

            # 도구 호출 없음 → 최종 답변
            if not tool_blocks:
                final_text = current_reasoning
                all_steps.append({
                    "step": step,
                    "type": "final_answer",
                    "reasoning": current_reasoning,
                    "answer": final_text,
                })
                break

            # ── 도구 실행 + 로깅 ──
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for tb in tool_blocks:
                tool_name = tb.name
                tool_input = tb.input

                # 도구 실행 — @tool wrapper가 dict→Pydantic 변환+검증
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
                    logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                latency_ms = (time.time() - start_ms) * 1000

                # trace 로깅 — reasoning(사고) + decision(도구 선택)
                self.trace_logger.log(
                    trace_id=trace_id,
                    step=step,
                    user_query=user_query,
                    selected_tool=tool_name,
                    tool_input=tool_input,
                    selection_reason=current_reasoning,
                    tool_output=tool_output,
                    tool_latency_ms=latency_ms,
                    tool_success=success,
                    error_message=error_msg,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )

                # 시각화용 step 기록
                # tool_output: 프론트엔드 차트 렌더링용 전체 데이터
                # tool_output_summary: Zone C 트레이스 패널용 한 줄 요약
                all_steps.append({
                    "step": step,
                    "type": "tool_call",
                    "reasoning": current_reasoning,
                    "tool": tool_name,
                    "tool_input": tool_input,
                    "tool_output": tool_output,
                    "tool_output_summary": self._summarize_output(tool_name, tool_output),
                    "mcp_server": self._tool_to_server.get(tool_name, "unknown"),
                    "latency_ms": round(latency_ms),
                    "success": success,
                })

                # tool_result 메시지 구성 → 다음 LLM 호출에 주입
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(tool_output, ensure_ascii=False, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            final_text = "최대 분석 단계를 초과했습니다. 질문을 더 구체적으로 해주세요."
            all_steps.append({
                "step": step,
                "type": "final_answer",
                "reasoning": "MAX_STEPS 초과로 강제 종료",
                "answer": final_text,
            })

        total_cost = total_input * 3 / 1_000_000 + total_output * 15 / 1_000_000

        logger.info(
            "orchestrator_complete",
            trace_id=trace_id,
            query=user_query[:50],
            total_steps=step,
            tools_used=[s["tool"] for s in all_steps if s["type"] == "tool_call"],
            total_cost_usd=round(total_cost, 6),
        )

        result = OrchestratorResult(
            answer=final_text,
            trace_id=trace_id,
            steps=all_steps,
            total_steps=step,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=round(total_cost, 6),
        )

        # 전체 결과를 orchestrator_results에 저장 — 재조회 시 동일 결과 제공
        try:
            self.trace_logger.save_result(
                trace_id=trace_id,
                user_query=user_query,
                answer=final_text,
                steps=all_steps,
                total_steps=step,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_cost_usd=round(total_cost, 6),
            )
        except Exception as e:
            logger.error("save_result_failed", trace_id=trace_id, error=str(e))

        return result

    @staticmethod
    def _summarize_output(tool_name: str, output: dict | list) -> str:
        """도구 출력을 프론트엔드 시각화용 한 줄 요약으로 변환."""
        if isinstance(output, dict) and "error" in output:
            return f"ERROR: {output['error'][:100]}"

        if tool_name == "query_causal_chain" and isinstance(output, list):
            if not output:
                return "인과 체인 없음"
            top = output[0]
            return (
                f"{top.get('skinConcern', '?')}({top.get('triggerStrength', '?')})"
                f"→{top.get('function', '?')}({top.get('demandStrength', '?')}) "
                f"외 {len(output)-1}건"
            )

        if tool_name == "get_attribute_trend" and isinstance(output, dict):
            trend = output.get("trend", {})
            parts = []
            for country, months in trend.items():
                if months:
                    first = months[0]["percentage"]
                    last = months[-1]["percentage"]
                    parts.append(f"{country}: {first}%→{last}%")
            return ", ".join(parts) if parts else "데이터 없음"

        if tool_name == "get_country_attribute_heatmap" and isinstance(output, dict):
            matrix = output.get("matrix", {})
            return f"{len(matrix)}개국 × {sum(len(v) for v in matrix.values())}개 속성"

        if tool_name == "find_trending_ingredients" and isinstance(output, list):
            if not output:
                return "성분 데이터 없음"
            return ", ".join(f"{r['ingredient']}({r['productCount']})" for r in output[:3])

        if tool_name == "find_ingredient_synergies" and isinstance(output, list):
            return f"{len(output)}개 시너지 성분"

        if tool_name == "get_product_graph" and isinstance(output, dict):
            return output.get("name", "상품 정보 없음")[:50]

        if isinstance(output, dict) and output.get("status") == "phase2":
            return "Phase 2 예정"

        return json.dumps(output, ensure_ascii=False, default=str)[:100]
