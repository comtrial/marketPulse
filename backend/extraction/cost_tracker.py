"""LLM API 비용 추적.

모든 추출 호출의 토큰 수, 비용, 레이턴시를 계산.
extractions 테이블에 저장되어 운영 비용 모니터링에 사용됨.

Claude Sonnet 4 기준 가격:
  - Input:  $3.00 / 1M tokens
  - Output: $15.00 / 1M tokens
"""

from extraction.schemas import ExtractionCost


class CostTracker:

    # Claude Sonnet 4 가격 (2026-03 기준)
    INPUT_COST_PER_1M = 3.0
    OUTPUT_COST_PER_1M = 15.0

    def calculate(
        self,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> ExtractionCost:
        """토큰 수와 레이턴시로 비용을 계산.

        Args:
            input_tokens: 입력 토큰 수 (system + user + tool schema)
            output_tokens: 출력 토큰 수 (tool_use 블록)
            latency_ms: API 호출 총 레이턴시 (밀리초)

        Returns:
            ExtractionCost with cost_usd rounded to 6 decimal places
        """
        cost = (
            input_tokens * self.INPUT_COST_PER_1M / 1_000_000
            + output_tokens * self.OUTPUT_COST_PER_1M / 1_000_000
        )
        return ExtractionCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            latency_ms=round(latency_ms),
        )
