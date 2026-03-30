"""Extraction pipeline data classes."""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionCost:
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float


@dataclass
class ExtractionTrace:
    """추출 파이프라인 각 단계의 상세 데이터. 프론트엔드 Zone C 시각화용."""

    vector_search: list[dict] = field(default_factory=list)  # gold_id, raw_input, similarity, combined_score, extracted_output
    few_shot_prompt: str = ""  # LLM에 주입된 few-shot 예시 블록
    llm_response: dict = field(default_factory=dict)  # input_tokens, output_tokens, model
    validation_details: dict = field(default_factory=dict)  # passed, errors, warnings


@dataclass
class ExtractionResult:
    attributes: dict
    validation: ValidationResult
    examples_used: list[str]
    avg_similarity: float
    cost: ExtractionCost
    graph_synced: bool
    trace: ExtractionTrace = field(default_factory=ExtractionTrace)
