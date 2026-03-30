"""Eval 스냅샷 저장/비교.

Step 4에서 "before_pattern_scout" 스냅샷 저장.
Step 6에서 "after_pattern_scout" 스냅샷 저장.
compare_snapshots()로 4축 차이를 자동 계산.
"""

import json
from datetime import datetime
from pathlib import Path

import structlog
from neo4j import Driver
from sqlalchemy.engine import Engine

from eval.metrics import run_full_eval

logger = structlog.get_logger()

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def save_snapshot(engine: Engine, driver: Driver, name: str) -> dict:
    """현재 시점의 4축 eval 결과를 JSON 파일로 저장.

    Args:
        engine: PostgreSQL sync engine
        driver: Neo4j driver
        name: 스냅샷 이름 (예: "before_pattern_scout")

    Returns:
        저장된 eval 결과 dict
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    result = run_full_eval(engine, driver)
    result["snapshot_name"] = name
    result["saved_at"] = datetime.now().isoformat()

    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = SNAPSHOTS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info("snapshot_saved", name=name, path=str(filepath))
    return result


def _find_latest_snapshot(name: str) -> Path | None:
    """이름으로 시작하는 가장 최신 스냅샷 파일을 찾는다."""
    if not SNAPSHOTS_DIR.exists():
        return None
    matches = sorted(SNAPSHOTS_DIR.glob(f"{name}_*.json"), reverse=True)
    return matches[0] if matches else None


def compare_snapshots(before_name: str, after_name: str) -> dict:
    """두 스냅샷의 4축 차이를 계산.

    Args:
        before_name: before 스냅샷 이름 (예: "before_pattern_scout")
        after_name: after 스냅샷 이름 (예: "after_pattern_scout")

    Returns:
        축별 before/after/delta
    """
    before_path = _find_latest_snapshot(before_name)
    after_path = _find_latest_snapshot(after_name)

    if not before_path or not after_path:
        missing = []
        if not before_path:
            missing.append(before_name)
        if not after_path:
            missing.append(after_name)
        return {"error": f"Snapshot not found: {', '.join(missing)}"}

    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    def _delta(b, a):
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            return round(a - b, 4)
        return None

    comparison = {
        "before_snapshot": before.get("snapshot_name"),
        "after_snapshot": after.get("snapshot_name"),
        "before_saved_at": before.get("saved_at"),
        "after_saved_at": after.get("saved_at"),
        "axes": {},
    }

    # 축 1: 패턴 탐지
    bp = before.get("pattern_discovery", {})
    ap = after.get("pattern_discovery", {})
    comparison["axes"]["pattern_discovery"] = {
        "total_proposed": {"before": bp.get("total_proposed", 0), "after": ap.get("total_proposed", 0), "delta": _delta(bp.get("total_proposed", 0), ap.get("total_proposed", 0))},
        "approved": {"before": bp.get("approved", 0), "after": ap.get("approved", 0), "delta": _delta(bp.get("approved", 0), ap.get("approved", 0))},
        "discovered_relations": {"before": bp.get("discovered_relations", 0), "after": ap.get("discovered_relations", 0), "delta": _delta(bp.get("discovered_relations", 0), ap.get("discovered_relations", 0))},
    }

    # 축 2: 답변 품질
    bq = before.get("answer_quality", {})
    aq = after.get("answer_quality", {})
    comparison["axes"]["answer_quality"] = {
        "discovered_usage_rate": {"before": bq.get("discovered_usage_rate", 0), "after": aq.get("discovered_usage_rate", 0), "delta": _delta(bq.get("discovered_usage_rate", 0), aq.get("discovered_usage_rate", 0))},
    }

    # 축 3: 추론 커버리지
    br = before.get("reasoning_coverage", {})
    ar = after.get("reasoning_coverage", {})
    comparison["axes"]["reasoning_coverage"] = {
        "full_coverage_rate": {"before": br.get("full_coverage_rate", 0), "after": ar.get("full_coverage_rate", 0), "delta": _delta(br.get("full_coverage_rate", 0), ar.get("full_coverage_rate", 0))},
        "causal_evidence_rate": {"before": br.get("causal_evidence_rate", 0), "after": ar.get("causal_evidence_rate", 0), "delta": _delta(br.get("causal_evidence_rate", 0), ar.get("causal_evidence_rate", 0))},
    }

    # 축 4: 시스템 효율
    be = before.get("system_efficiency", {})
    ae = after.get("system_efficiency", {})
    if be.get("status") == "ok" and ae.get("status") == "ok":
        comparison["axes"]["system_efficiency"] = {
            "cost_reduction": {"before": be.get("cost_reduction", 0), "after": ae.get("cost_reduction", 0), "delta": _delta(be.get("cost_reduction", 0), ae.get("cost_reduction", 0))},
        }
    else:
        comparison["axes"]["system_efficiency"] = {"status": "insufficient_data"}

    return comparison
