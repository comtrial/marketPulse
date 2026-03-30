"""Eval 메트릭 단위 테스트.

테이블/데이터가 없는 상태에서도 Eval이 정상 동작하는지 검증.
PatternScout 미구현 상태를 시뮬레이션.
"""

from unittest.mock import MagicMock, patch

import pytest

from eval.metrics import (
    _has_discovered_links,
    eval_answer_quality,
    eval_pattern_discovery,
    eval_reasoning_coverage,
    eval_system_efficiency,
    find_before_after_pairs,
    run_full_eval,
)


# ── Mock 헬퍼 ──


def make_mock_engine(rows=None, scalar=None):
    """SQLAlchemy Engine mock."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    if rows is not None:
        result = MagicMock()
        result.mappings.return_value.all.return_value = rows
        result.mappings.return_value.one.return_value = rows[0] if rows else {}
        conn.execute.return_value = result
    if scalar is not None:
        result = MagicMock()
        result.scalar.return_value = scalar
        conn.execute.return_value = result

    return engine


def make_mock_driver(query_results=None):
    """Neo4j Driver mock."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    if query_results:
        session.run.side_effect = query_results
    else:
        # 기본: 모든 쿼리가 0/False 반환
        default_result = MagicMock()
        default_result.single.return_value = {"c": 0, "exists": False}
        default_result.__iter__ = MagicMock(return_value=iter([]))
        session.run.return_value = default_result

    return driver


# ── _has_discovered_links 테스트 ──


class TestHasDiscoveredLinks:

    def test_empty_steps(self):
        assert _has_discovered_links([]) is False

    def test_no_causal_chain_step(self):
        steps = [{"type": "tool_call", "tool": "get_attribute_trend", "tool_output": {}}]
        assert _has_discovered_links(steps) is False

    def test_causal_chain_without_discovered(self):
        steps = [
            {
                "type": "tool_call",
                "tool": "query_causal_chain",
                "tool_output": [{"chainStrength": 0.81, "discovered_links": []}],
            }
        ]
        assert _has_discovered_links(steps) is False

    def test_causal_chain_with_discovered(self):
        steps = [
            {
                "type": "tool_call",
                "tool": "query_causal_chain",
                "tool_output": [
                    {"chainStrength": 0.81, "discovered_links": [{"type": "SYNERGY", "lift": 1.54}]}
                ],
            }
        ]
        assert _has_discovered_links(steps) is True

    def test_final_answer_ignored(self):
        steps = [{"type": "final_answer", "answer": "test"}]
        assert _has_discovered_links(steps) is False


# ── 축 1: 패턴 탐지 ──


class TestPatternDiscovery:

    @patch("eval.metrics._table_exists", return_value=False)
    def test_no_table_returns_zeros(self, mock_exists):
        """relationship_proposals 테이블 없으면 전부 0."""
        driver = make_mock_driver()
        engine = make_mock_engine()

        # Neo4j seed=34, discovered=0
        seed_result = MagicMock()
        seed_result.single.return_value = {"c": 34}
        disc_result = MagicMock()
        disc_result.single.return_value = {"c": 0}
        session = driver.session.return_value.__enter__.return_value
        session.run.side_effect = [seed_result, disc_result]

        result = eval_pattern_discovery(engine, driver)

        assert result["total_proposed"] == 0
        assert result["approved"] == 0
        assert result["discovered_relations"] == 0
        assert result["seed_relations"] == 34


# ── 축 2: 답변 품질 ──


class TestAnswerQuality:

    def test_empty_results(self):
        """orchestrator_results가 비어있으면 rate 0."""
        engine = make_mock_engine(rows=[])
        result = eval_answer_quality(engine)

        assert result["total_analyses"] == 0
        assert result["discovered_usage_rate"] == 0

    def test_no_discovered_usage(self):
        """discovered_links가 없는 결과만 있을 때."""
        engine = make_mock_engine(rows=[
            {"trace_id": "t1", "steps": [{"type": "tool_call", "tool": "get_attribute_trend", "tool_output": {}}]},
        ])
        result = eval_answer_quality(engine)

        assert result["total_analyses"] == 1
        assert result["used_discovered_link"] == 0
        assert result["discovered_usage_rate"] == 0


# ── 축 3: 추론 커버리지 ──


class TestReasoningCoverage:

    @patch("eval.metrics._get_countries", return_value=["KR", "JP", "SG"])
    @patch("eval.metrics._get_product_types", return_value=[
        {"en": "sunscreen", "ko": "선크림"},
        {"en": "toner", "ko": "토너"},
    ])
    def test_matrix_structure(self, mock_types, mock_countries):
        """매트릭스 키가 국가×유형 조합인지."""
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        # PG 쿼리: 첫 2개는 count(*), 나머지는 exists
        count_result = MagicMock()
        count_result.mappings.return_value.one.return_value = {"c": 0}
        exists_result = MagicMock()
        exists_result.mappings.return_value.one.return_value = {"exists": True}
        conn.execute.side_effect = [count_result, count_result] + [exists_result] * 6

        driver = make_mock_driver()
        session = driver.session.return_value.__enter__.return_value
        causal_r = MagicMock()
        causal_r.single.return_value = {"exists": True}
        disc_r = MagicMock()
        disc_r.single.return_value = {"exists": False}
        session.run.side_effect = [causal_r, disc_r] * 6

        result = eval_reasoning_coverage(engine, driver)

        assert "matrix" in result
        assert "KR_sunscreen" in result["matrix"]
        assert "JP_toner" in result["matrix"]
        assert result["total_cells"] == 6  # 3 × 2


# ── 축 4: 시스템 효율 ──


class TestSystemEfficiency:

    def test_insufficient_data(self):
        """데이터 1건 미만이면 insufficient_data."""
        engine = make_mock_engine(rows=[])
        result = eval_system_efficiency(engine)

        assert result["status"] == "insufficient_data"


# ── Before/After ──


class TestBeforeAfterPairs:

    def test_no_pairs(self):
        """반복 실행된 질문이 없으면 빈 리스트."""
        engine = make_mock_engine(rows=[])
        result = find_before_after_pairs(engine)

        assert result == []


# ── 통합 Eval ──


class TestFullEval:

    @patch("eval.metrics.eval_pattern_discovery", return_value={"total_proposed": 0})
    @patch("eval.metrics.eval_answer_quality", return_value={"discovered_usage_rate": 0})
    @patch("eval.metrics.eval_reasoning_coverage", return_value={"full_coverage_rate": 0})
    @patch("eval.metrics.eval_system_efficiency", return_value={"status": "insufficient_data"})
    @patch("eval.metrics.find_before_after_pairs", return_value=[])
    def test_full_eval_keys(self, *mocks):
        """run_full_eval이 5개 키를 전부 반환하는지."""
        engine = MagicMock()
        driver = MagicMock()

        result = run_full_eval(engine, driver)

        assert "pattern_discovery" in result
        assert "answer_quality" in result
        assert "reasoning_coverage" in result
        assert "system_efficiency" in result
        assert "before_after_pairs" in result
