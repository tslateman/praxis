"""Synthesize actionable views from Lore's data.

Combines intent, failures, inbox, and journal into views that answer:
- status: Where am I? What's blocking?
- next: What should I work on?
- blockers: What's in the way?
- health: Ecosystem pulse
- triggers: Recurring failure types
- friction: Project boundary issues
- blind_spots: Failures without decisions
- stale: Observations aging without action
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from praxis import lore


def _parse_ts(iso_str: str) -> datetime:
    """Parse an ISO timestamp, treating naive timestamps as UTC."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now() -> datetime:
    """Current time in UTC."""
    return datetime.now(timezone.utc)


# --- Operational Views ---

def status() -> dict:
    """Where am I? Active goals, current blockers, ecosystem pulse.
    
    Returns dict with:
      active_goals: list of active goals with their missions
      blockers: summary of failures, stale items, friction
      pulse: quick health indicator
    """
    active = lore.active_goals()
    pending = lore.pending_missions()
    fails = lore.failures()
    stale_obs = _stale_observations(days=7)
    
    # Recent failures (last 7 days)
    week_ago = _now() - timedelta(days=7)
    recent_failures = []
    for f in fails:
        try:
            ts = _parse_ts(f.get("timestamp", ""))
            if ts >= week_ago:
                recent_failures.append(f)
        except (ValueError, TypeError):
            continue
    
    # Determine pulse
    if len(recent_failures) > 5 or len(stale_obs) > 10:
        pulse = "attention"
    elif len(recent_failures) > 0 or len(stale_obs) > 0:
        pulse = "active"
    else:
        pulse = "clear"
    
    return {
        "active_goals": active,
        "pending_missions": pending,
        "blockers": {
            "recent_failures": len(recent_failures),
            "stale_observations": len(stale_obs),
        },
        "pulse": pulse,
    }


def next_work() -> list[dict]:
    """What should I work on? Prioritized work queue.
    
    Priority:
    1. In-progress missions (finish what you started)
    2. Pending missions from high-priority goals
    3. Pending missions from other goals
    """
    missions_list = lore.missions()
    goals_list = {g.get("id"): g for g in lore.goals()}
    
    def priority_key(m: dict) -> tuple:
        goal = goals_list.get(m.get("goal_id", ""), {})
        goal_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
            goal.get("priority", "medium"), 2
        )
        status_priority = 0 if m.get("status") == "in_progress" else 1
        return (status_priority, goal_priority, m.get("id", ""))
    
    pending = [m for m in missions_list if m.get("status") not in ("completed", "failed", "cancelled")]
    return sorted(pending, key=priority_key)


def blockers_view() -> dict:
    """What's in the way? Failures, stale observations, friction points.
    
    Returns dict with:
      failures: recent failures grouped by type
      stale: observations needing attention
      friction: project boundaries with issues
    """
    fails = lore.failures()
    week_ago = _now() - timedelta(days=7)
    
    recent_failures = []
    for f in fails:
        try:
            ts = _parse_ts(f.get("timestamp", ""))
            if ts >= week_ago:
                recent_failures.append(f)
        except (ValueError, TypeError):
            continue
    
    by_type = Counter(f.get("error_type", "unknown") for f in recent_failures)
    
    return {
        "failures": {
            "recent": recent_failures,
            "by_type": dict(by_type.most_common()),
            "count": len(recent_failures),
        },
        "stale": {
            "observations": _stale_observations(days=7),
            "count": len(_stale_observations(days=7)),
        },
        "friction": friction(),
    }


# --- Analysis Views ---

def health() -> dict:
    """Single-page ecosystem health summary.
    
    Aggregates: failure count, triggers, stale observations, blind spots,
    friction hotspots. Returns status indicator (healthy/attention/critical).
    """
    fails = lore.failures()
    week_ago = _now() - timedelta(days=7)
    
    recent = []
    for f in fails:
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
        status_val = "critical"
    elif stale_results["stale_count"] > 0 or len(trigger_results) > 0:
        status_val = "attention"
    else:
        status_val = "healthy"
    
    return {
        "summary": {
            "total_failures": len(fails),
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
        "status": status_val,
    }


def triggers(threshold: int = 3) -> list[dict]:
    """Error types that hit the Rule of Three.
    
    When an error type recurs >= threshold times, it signals a
    systemic issue worth addressing.
    """
    fails = lore.failures()
    by_type: dict[str, list[dict]] = {}
    
    for f in fails:
        et = f.get("error_type", "unknown")
        by_type.setdefault(et, []).append(f)
    
    results = []
    for et, entries in sorted(by_type.items()):
        if len(entries) >= threshold:
            missions_set = sorted(set(e.get("mission", "") for e in entries))
            results.append({
                "error_type": et,
                "count": len(entries),
                "missions": missions_set,
            })
    
    return results


def _stale_observations(days: int = 7) -> list[dict]:
    """Helper: observations older than threshold with status='raw'."""
    entries = lore.raw_observations()
    threshold = timedelta(days=days)
    now = _now()
    
    stale_obs = []
    for e in entries:
        try:
            ts = _parse_ts(e.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        if (now - ts) > threshold:
            stale_obs.append(e)
    
    return sorted(stale_obs, key=lambda e: e.get("timestamp", ""))


def stale(days: int = 7) -> dict:
    """Observations aging without action.
    
    Returns dict with stale_observations, stale_count, total_raw.
    """
    raw_entries = lore.raw_observations()
    stale_obs = _stale_observations(days)
    
    return {
        "stale_observations": stale_obs,
        "stale_count": len(stale_obs),
        "total_raw": len(raw_entries),
    }


def friction() -> list[dict]:
    """Which project boundaries generate the most failures?
    
    Joins failures to registry relationships by extracting project names
    from mission identifiers.
    """
    fails = lore.failures()
    reg = lore.registry()
    
    if not fails:
        return []
    
    deps = reg.get("dependencies", {})
    project_names = set(deps.keys())
    
    boundary_failures: dict[str, list[dict]] = {}
    for f in fails:
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
        missions_set = sorted(set(f.get("mission", "") for f in flist))
        results.append({
            "boundary": boundary,
            "failure_count": len(flist),
            "error_types": dict(error_counts),
            "missions": missions_set,
        })
    
    return results


def blind_spots(threshold: int = 3) -> dict:
    """Failures that recur without a corresponding journal entry.
    
    Groups failures by error_type + mission, finds those with >= threshold
    occurrences and no nearby journal entry (±24h).
    """
    fails = lore.failures()
    decs = lore.decisions()
    
    if not fails:
        return {
            "orphaned_failures": [],
            "blind_spot_count": 0,
            "suggestions": [],
        }
    
    window = timedelta(hours=24)
    
    grouped: dict[str, list[dict]] = {}
    for f in fails:
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
            
            for d in decs:
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


def correlate(window_hours: int = 24) -> list[dict]:
    """Failures alongside journal entries within a time window.
    
    For each failure, find journal decisions made within window_hours
    before or after the failure timestamp.
    """
    fails = lore.failures()
    if not fails:
        return []
    
    decs = lore.decisions()
    window = timedelta(hours=window_hours)
    results = []
    
    for f in fails:
        try:
            f_time = _parse_ts(f.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        
        nearby = []
        for d in decs:
            try:
                d_time = _parse_ts(d.get("timestamp", ""))
            except (ValueError, TypeError):
                continue
            if abs(f_time - d_time) <= window:
                nearby.append(d)
        
        results.append({"failure": f, "nearby_decisions": nearby})
    
    results.sort(key=lambda r: r["failure"].get("timestamp", ""))
    return results
