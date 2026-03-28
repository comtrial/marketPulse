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
class ExtractionResult:
    attributes: dict
    validation: ValidationResult
    examples_used: list[str]
    avg_similarity: float
    cost: ExtractionCost
    graph_synced: bool
