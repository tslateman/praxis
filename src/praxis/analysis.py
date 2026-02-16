"""Query and detect patterns in failure journals.

Seven views into accumulated failures:
- summarize: filter and count by error type or mission
- triggers: error types that hit the Rule of Three threshold
- timeline: chronological failure history for a mission
- correlate: failures alongside journal entries within a time window
- stale: observations aging without action
- friction: failures mapped to project boundaries
- blind_spots: recurring failures without journal entries
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from praxis.failure import read_failures
from praxis.sources import read_journal, read_inbox, read_registry


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


def friction() -> list[dict]:
    """Which project boundaries generate the most failures?

    Joins failures to registry relationships by extracting project names
    from mission identifiers. Returns list of dicts with 'boundary',
    'failure_count', 'error_types', 'missions'.
    """
    failures = read_failures()
    registry = read_registry()

    if not failures:
        return []

    deps = registry.get("dependencies", {})
    project_names = set(deps.keys())

    boundary_failures: dict[str, list[dict]] = {}
    for f in failures:
        mission = f.get("mission", "")

        boundary = None
        for proj in project_names:
            if proj in mission:
                boundary = proj
                break

        if boundary:
            boundary_failures.setdefault(boundary, []).append(f)

    results = []
    for boundary, flist in sorted(boundary_failures.items(), key=lambda x: -len(x[1])):
        error_counts = Counter(f.get("error_type", "unknown") for f in flist)
        missions = sorted(set(f.get("mission", "") for f in flist))
        results.append({
            "boundary": boundary,
            "failure_count": len(flist),
            "error_types": dict(error_counts),
            "missions": missions,
        })

    return results


def blind_spots(threshold: int = 3) -> dict:
    """Failures that recur without a corresponding journal entry.

    Groups failures by error_type + mission, finds those with >= threshold
    occurrences and no nearby journal entry (±24h). Returns dict with
    'orphaned_failures', 'blind_spot_count', 'suggestions'.
    """
    failures = read_failures()
    decisions = read_journal()

    if not failures:
        return {
            "orphaned_failures": [],
            "blind_spot_count": 0,
            "suggestions": [],
        }

    window = timedelta(hours=24)

    grouped: dict[str, list[dict]] = {}
    for f in failures:
        key = f"{f.get('error_type', 'unknown')}::{f.get('mission', '')}"
        grouped.setdefault(key, []).append(f)

    orphaned = []
    suggestions = []

    for key, flist in grouped.items():
        if len(flist) < threshold:
            continue

        has_nearby = False
        first_ts = None
        latest_ts = None

        for f in flist:
            try:
                f_time = _parse_ts(f.get("timestamp", ""))
            except (ValueError, TypeError):
                continue

            if first_ts is None or f_time < first_ts:
                first_ts = f_time
            if latest_ts is None or f_time > latest_ts:
                latest_ts = f_time

            for d in decisions:
                try:
                    d_time = _parse_ts(d.get("timestamp", ""))
                except (ValueError, TypeError):
                    continue
                if abs(f_time - d_time) <= window:
                    has_nearby = True
                    break
            if has_nearby:
                break

        if not has_nearby and first_ts and latest_ts:
            error_type, mission = key.split("::", 1)
            orphaned.append({
                "error_type": error_type,
                "mission": mission,
                "count": len(flist),
                "first_occurrence": first_ts.isoformat(),
                "latest_occurrence": latest_ts.isoformat(),
            })
            suggestions.append(
                f"Investigate {error_type} failures for {mission}"
            )

    return {
        "orphaned_failures": orphaned,
        "blind_spot_count": len(orphaned),
        "suggestions": suggestions,
    }


def health() -> dict:
    """Single-page ecosystem health summary.

    Aggregates: failure count, triggers, stale observations, blind spots,
    friction hotspots. Returns dict with sections for each plus a status
    indicator (healthy/attention/critical).
    """
    failures = read_failures()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    recent = []
    for f in failures:
        try:
            ts = _parse_ts(f.get("timestamp", ""))
            if ts >= week_ago:
                recent.append(f)
        except (ValueError, TypeError):
            continue

    trigger_results = triggers()
    stale_results = stale()
    blind_spot_results = blind_spots()
    friction_results = friction()

    # Determine status
    has_critical_triggers = any(t["count"] >= 5 for t in trigger_results)
    has_blind_spots = blind_spot_results["blind_spot_count"] > 0

    if has_blind_spots or has_critical_triggers:
        status = "critical"
    elif stale_results["stale_count"] > 0 or len(trigger_results) > 0:
        status = "attention"
    else:
        status = "healthy"

    return {
        "summary": {
            "total_failures": len(failures),
            "recent_failures": len(recent),
            "trigger_count": len(trigger_results),
            "stale_count": stale_results["stale_count"],
            "blind_spot_count": blind_spot_results["blind_spot_count"],
            "friction_boundaries": len(friction_results),
        },
        "triggers": trigger_results,
        "stale_observations": stale_results["stale_observations"],
        "blind_spots": blind_spot_results["orphaned_failures"],
        "friction": friction_results,
        "status": status,
    }
