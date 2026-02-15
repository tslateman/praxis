"""Query and detect patterns in failure journals.

Three views into accumulated failures:
- summarize: filter and count by error type or mission
- triggers: error types that hit the Rule of Three threshold
- timeline: chronological failure history for a mission
"""

from collections import Counter

from praxis.failure import read_failures


def summarize(error_type: str | None = None, mission: str | None = None) -> dict:
    """Filter failures and return counts by error type.

    Returns dict with 'total', 'by_type' counts, and 'failures' list.
    """
    failures = read_failures()

    if error_type:
        failures = [f for f in failures if f.get("error_type") == error_type]
    if mission:
        failures = [f for f in failures if f.get("mission") == mission]

    by_type = Counter(f.get("error_type", "unknown") for f in failures)

    return {
        "total": len(failures),
        "by_type": dict(by_type.most_common()),
        "failures": failures,
    }


def triggers(threshold: int = 3) -> list[dict]:
    """Error types that hit the Rule of Three.

    When an error type recurs >= threshold times, it signals a
    systemic issue worth addressing -- better tooling, clearer
    plans, or a different approach.

    Returns list of dicts with 'error_type', 'count', 'missions'.
    """
    failures = read_failures()
    by_type: dict[str, list[dict]] = {}

    for f in failures:
        et = f.get("error_type", "unknown")
        by_type.setdefault(et, []).append(f)

    results = []
    for et, entries in sorted(by_type.items()):
        if len(entries) >= threshold:
            missions = sorted(set(e.get("mission", "") for e in entries))
            results.append({
                "error_type": et,
                "count": len(entries),
                "missions": missions,
            })

    return results


def timeline(mission: str) -> list[dict]:
    """Chronological failure history for a mission.

    Returns failures sorted by timestamp, oldest first.
    """
    failures = read_failures()
    mission_failures = [f for f in failures if f.get("mission") == mission]
    return sorted(mission_failures, key=lambda f: f.get("timestamp", ""))
