"""CostTracker 단위 테스트."""

from extraction.cost_tracker import CostTracker


def test_sonnet_cost_calculation():
    """Sonnet 4 기준 비용 계산 정확성."""
    tracker = CostTracker()
    cost = tracker.calculate(
        input_tokens=1200,
        output_tokens=150,
        latency_ms=800.5,
    )

    # input: 1200 * 3.0 / 1_000_000 = 0.0036
    # output: 150 * 15.0 / 1_000_000 = 0.00225
    # total: 0.00585
    assert cost.cost_usd == 0.00585
    assert cost.input_tokens == 1200
    assert cost.output_tokens == 150
    assert cost.latency_ms == 800  # round(800.5) = 800 (banker's rounding)


def test_zero_tokens():
    """토큰 0일 때 비용 0."""
    tracker = CostTracker()
    cost = tracker.calculate(input_tokens=0, output_tokens=0, latency_ms=0)

    assert cost.cost_usd == 0.0


def test_large_batch_cost():
    """1,000건 배치 비용 추정 — 건당 input 1200, output 150 가정."""
    tracker = CostTracker()
    total = 0.0
    for _ in range(1000):
        cost = tracker.calculate(
            input_tokens=1200, output_tokens=150, latency_ms=800
        )
        total += cost.cost_usd

    # 1000 * 0.00585 = 5.85
    assert 5.8 < total < 5.9
