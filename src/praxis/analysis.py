"""Query and detect patterns in failure journals.

Five views into accumulated failures:
- summarize: filter and count by error type or mission
- triggers: error types that hit the Rule of Three threshold
- timeline: chronological failure history for a mission
- correlate: failures alongside journal entries within a time window
- stale: observations aging without action
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from praxis.failure import read_failures
from praxis.sources import read_journal, read_inbox


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


def _parse_ts(iso_str: str) -> datetime:
    """Parse an ISO timestamp, treating naive timestamps as UTC."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def correlate(window_hours: int = 24) -> list[dict]:
    """Failures alongside journal entries within a time window.

    For each failure, find journal decisions made within window_hours
    before or after the failure timestamp. Returns list of dicts with
    'failure' and 'nearby_decisions' keys.
    """
    failures = read_failures()
    if not failures:
        return []

    decisions = read_journal()
    window = timedelta(hours=window_hours)
    results = []

    for f in failures:
        try:
            f_time = _parse_ts(f.get("timestamp", ""))
        except (ValueError, TypeError):
            continue

        nearby = []
        for d in decisions:
            try:
                d_time = _parse_ts(d.get("timestamp", ""))
            except (ValueError, TypeError):
                continue
            if abs(f_time - d_time) <= window:
                nearby.append(d)

        results.append({"failure": f, "nearby_decisions": nearby})

    results.sort(key=lambda r: r["failure"].get("timestamp", ""))
    return results


def stale(days: int = 7) -> dict:
    """Observations and judgments aging without action.

    Returns dict with 'stale_observations' (inbox entries older than
    threshold with status='raw') and 'stale_count'.
    """
    entries = read_inbox()
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=days)

    raw_entries = [e for e in entries if e.get("status") == "raw"]
    stale_obs = []

    for e in raw_entries:
        try:
            ts = _parse_ts(e.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        if (now - ts) > threshold:
            stale_obs.append(e)

    stale_obs.sort(key=lambda e: e.get("timestamp", ""))
    return {
        "stale_observations": stale_obs,
        "stale_count": len(stale_obs),
        "total_raw": len(raw_entries),
    }
