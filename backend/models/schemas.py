"""API request/response Pydantic schemas."""

from pydantic import BaseModel


# ── Extract ──


class ExtractRequest(BaseModel):
    product_name: str


class ExtractResponse(BaseModel):
    attributes: dict
    validation_passed: bool
    errors: list[str]
    warnings: list[str]
    examples_used: list[str]
    avg_similarity: float
    cost_usd: float
    latency_ms: float
    graph_synced: bool


class BatchExtractRequest(BaseModel):
    platform: str | None = None  # "cafe24", "qoo10", "shopee" — None이면 전체
    limit: int = 100


class BatchExtractResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    total_cost_usd: float


class ExtractStatsResponse(BaseModel):
    total_extractions: int
    total_cost_usd: float
    graph_synced_count: int
    graph_synced_ratio: float
    error_count: int
    error_ratio: float
    avg_latency_ms: float
