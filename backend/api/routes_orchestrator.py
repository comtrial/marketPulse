"""오케스트레이터 API — 자연어 질문 → LLM 도구 선택 → 인사이트.

POST /ask: LLM이 도구를 자동 선택·호출하여 답변 생성
GET /traces: 최근 분석 이력
GET /trace/{trace_id}: 특정 분석의 판단 흐름 상세 (시각화용)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from orchestrator.llm_orchestrator import LLMOrchestrator
from orchestrator.trace_logger import TraceLogger

router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestrator"])

_orchestrator: LLMOrchestrator | None = None
_trace_logger: TraceLogger | None = None


def get_orchestrator() -> LLMOrchestrator:
    if _orchestrator is None:
        raise RuntimeError("LLMOrchestrator not initialized.")
    return _orchestrator


def get_trace_logger() -> TraceLogger:
    if _trace_logger is None:
        raise RuntimeError("TraceLogger not initialized.")
    return _trace_logger


def init_orchestrator(orchestrator: LLMOrchestrator, trace_logger: TraceLogger) -> None:
    global _orchestrator, _trace_logger
    _orchestrator = orchestrator
    _trace_logger = trace_logger


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    answer: str
    trace_id: str
    steps: list[dict]
    total_steps: int
    total_cost_usd: float


@router.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    orchestrator: LLMOrchestrator = Depends(get_orchestrator),
):
    """자연어 질문 → LLM이 도구를 자동 선택·호출 → 인사이트 응답.

    steps 필드에 각 step의 reasoning(사고)+tool(결정)+결과가 포함되어
    프론트엔드에서 의사결정 흐름도를 렌더링할 수 있다.
    """
    result = await orchestrator.ask(user_query=req.query)

    return AskResponse(
        answer=result.answer,
        trace_id=result.trace_id,
        steps=result.steps,
        total_steps=result.total_steps,
        total_cost_usd=result.total_cost_usd,
    )


@router.get("/traces")
def list_traces(
    limit: int = 20,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """최근 분석 이력 목록."""
    return trace_logger.get_recent_traces(limit=limit)


@router.get("/trace/{trace_id}")
def get_trace(
    trace_id: str,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """특정 trace의 판단 흐름 상세. 프론트엔드 흐름도 시각화용."""
    return trace_logger.get_trace(trace_id=trace_id)
