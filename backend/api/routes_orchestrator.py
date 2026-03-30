"""오케스트레이터 API — 자연어 질문 → LLM 도구 선택 → 인사이트.

POST /ask: LLM이 도구를 자동 선택·호출하여 답변 생성
GET /result/{trace_id}: 저장된 결과 재조회 (POST /ask와 동일 형식)
GET /results: 최근 분석 이력 목록
GET /traces: 최근 trace 목록 (디버깅용)
GET /trace/{trace_id}: 특정 trace step별 상세 (디버깅용)
"""

from fastapi import APIRouter, Depends, HTTPException
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
    user_query: str | None = None
    steps: list[dict]
    total_steps: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    scout_trace_id: str | None = None
    scout_proposals: int = 0


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
        total_input_tokens=result.total_input_tokens,
        total_output_tokens=result.total_output_tokens,
        total_cost_usd=result.total_cost_usd,
        scout_trace_id=result.scout_trace_id,
        scout_proposals=result.scout_proposals,
    )


@router.get("/result/{trace_id}", response_model=AskResponse)
def get_result(
    trace_id: str,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """저장된 분석 결과를 POST /ask와 동일한 형식으로 반환.

    Zone B 시각화 + Zone C 트레이스 완전 복원 가능.
    """
    result = trace_logger.get_result(trace_id=trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return AskResponse(**result)


@router.get("/results")
def list_results(
    limit: int = 20,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """최근 분석 결과 이력."""
    return trace_logger.get_recent_results(limit=limit)


@router.get("/traces")
def list_traces(
    limit: int = 20,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """최근 trace 목록 (디버깅용)."""
    return trace_logger.get_recent_traces(limit=limit)


@router.get("/trace/{trace_id}")
def get_trace(
    trace_id: str,
    trace_logger: TraceLogger = Depends(get_trace_logger),
):
    """특정 trace의 step별 상세 (디버깅용)."""
    return trace_logger.get_trace(trace_id=trace_id)
