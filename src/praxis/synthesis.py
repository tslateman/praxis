"""Synthesize actionable views from Lore's data.

Combines intent, failures, inbox, journal, and patterns into views that answer:
- status: Where am I? What's blocking?
- next: What should I work on?
- blockers: What's in the way?
- health: Ecosystem pulse (failures + hygiene)
- triggers: Recurring failure types
- friction: Project boundary issues
- blind_spots: Failures without decisions
- stale: Observations aging without action
- refinement: Decisions ripe for promotion to patterns
- context: Filtered context brief for agent prompts
- ecosystem_overlap: Command name conflicts
- ecosystem_complexity: Projects exceeding thresholds
- undocumented: Decisions/patterns without rationale
"""

import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

from praxis import lore, spectrace


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
      active_goals: list of active goals
      blockers: summary of failures, stale items, friction
      pulse: quick health indicator
    """
    active = lore.active_goals()
    fails = lore.failures()
    stale_obs = _stale_observations(days=7)
    tasks = spectrace.fetch_tasks()
    task_counts = Counter(t.get("status", "unknown") for t in tasks)

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
        "tasks": dict(task_counts),
        "blockers": {
            "recent_failures": len(recent_failures),
            "stale_observations": len(stale_obs),
        },
        "pulse": pulse,
    }


def next_work() -> list[dict]:
    """What should I work on? Prioritized work queue.

    Priority:
    1. In-progress SpecTrace tasks
    2. Unclaimed SpecTrace tasks
    3. Active goals sorted by priority
    """
    tasks = spectrace.fetch_tasks()

    in_progress = []
    unclaimed = []
    for t in tasks:
        status = t.get("status")
        item = {
            "type": "task",
            "id": t.get("external_id"),
            "name": t.get("title"),
            "status": status,
        }
        if status == "in_progress":
            in_progress.append(item)
        elif status == "unclaimed":
            unclaimed.append(item)

    goals_list = lore.active_goals()
    for g in goals_list:
        g["type"] = "goal"
        if "id" not in g:
            g["id"] = g.get("name", "")

    def priority_key(g: dict) -> tuple:
        goal_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
            g.get("priority", "medium"), 2
        )
        return (goal_priority, g.get("id", ""))

    sorted_goals = sorted(goals_list, key=priority_key)

    return in_progress + unclaimed + sorted_goals


def context(
    tags: list[str] | None = None,
    project: str | None = None,
    since_days: int | None = None,
    budget: int = 2000,
) -> dict:
    """Filtered context brief for agent prompts.

    Fills sections in priority order (patterns, anti-patterns, decisions,
    goals) until the token budget is reached. Composite relevance score:
      relevance = 5.0 * filter + 2.0 * recency + 1.5 * quality + 1.0 * activity
    """
    cutoff = None
    if since_days is not None:
        cutoff = _now() - timedelta(days=since_days)

    has_filter = bool(tags or project)
    now = _now()

    def _estimate_tokens(text: str) -> int:
        return len(text) // 4

    # --- Signal 1: Filter Match (weight 5.0) ---

    def _filter_score(item: dict) -> float:
        raw = 0
        if tags:
            item_tags = set(t.lower() for t in item.get("tags", []))
            item_cat = item.get("category", "").lower()
            item_text = " ".join(
                [
                    item.get("name", ""),
                    item.get("context", ""),
                    item.get("problem", ""),
                ]
            ).lower()
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in item_tags or tag_lower == item_cat:
                    raw += 2
                elif tag_lower in item_text:
                    raw += 1
        if project:
            proj_lower = project.lower()
            entities = [e.lower() for e in item.get("entities", [])]
            item_tags_l = [t.lower() for t in item.get("tags", [])]
            projects_list = [p.lower() for p in item.get("projects", [])]
            if (
                proj_lower in entities
                or proj_lower in item_tags_l
                or proj_lower in projects_list
            ):
                raw += 2
        max_raw = 2 * len(tags or []) + 2 * bool(project)
        return raw / max_raw if max_raw > 0 else 0.0

    # --- Signal 2: Recency Decay (weight 2.0, half-life 14 days) ---

    def _recency_score(item: dict) -> float:
        for field in ("timestamp", "created_at"):
            ts_str = item.get(field, "")
            if ts_str:
                try:
                    ts = _parse_ts(ts_str)
                    age_days = (now - ts).total_seconds() / 86400.0
                    return math.pow(0.5, age_days / 14.0)
                except (ValueError, TypeError):
                    continue
        return 0.0

    # --- Signal 3: Quality / Consequence (weight 1.5) ---

    _outcome_map = {
        "successful": 0.9,
        "accepted": 0.8,
        "pending": 0.5,
        "revised": 0.3,
    }
    _severity_map = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
    _priority_map = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
    _goal_status_map = {"active": 1.0, "paused": 0.3, "archived": 0.0}

    def _quality_score(item: dict, data_type: str) -> float:
        if data_type == "patterns":
            conf = float(item.get("confidence", 0))
            validations = float(item.get("validations", 0))
            spec_q = float(item.get("spec_quality", 0))
            return 0.5 * conf + 0.3 * min(validations / 10.0, 1.0) + 0.2 * spec_q
        if data_type == "anti_patterns":
            return _severity_map.get(item.get("severity", "medium"), 0.5)
        if data_type == "decisions":
            outcome_val = _outcome_map.get(item.get("outcome", ""), 0.5)
            spec_q = float(item.get("spec_quality", 0))
            has_lesson = 1.0 if item.get("lesson_learned") else 0.0
            return 0.6 * outcome_val + 0.3 * spec_q + 0.1 * has_lesson
        if data_type == "goals":
            pri_val = _priority_map.get(item.get("priority", "medium"), 0.5)
            sta_val = _goal_status_map.get(item.get("status", ""), 0.0)
            return 0.6 * pri_val + 0.4 * sta_val
        return 0.0

    # --- Signal 4: Activity Proximity (weight 1.0) ---

    def _build_active_context() -> tuple[set, set]:
        active_tags: set[str] = set()
        active_projects: set[str] = set()
        for g in lore.active_goals():
            for t in g.get("tags", []):
                active_tags.add(t.lower())
            cat = g.get("category", "")
            if cat:
                active_tags.add(cat.lower())
            for p in g.get("projects", []):
                active_projects.add(p.lower())
        return active_tags, active_projects

    active_tags, active_projects = _build_active_context()

    def _activity_score(item: dict) -> float:
        item_tags = set(t.lower() for t in item.get("tags", []))
        item_cat = item.get("category", "").lower()
        if item_cat:
            item_tags.add(item_cat)
        item_projects = set(p.lower() for p in item.get("projects", []))
        if item_tags & active_tags or item_projects & active_projects:
            return 1.0
        return 0.0

    # --- Composite Score ---

    def _composite_score(item: dict, data_type: str) -> float:
        return (
            5.0 * _filter_score(item)
            + 2.0 * _recency_score(item)
            + 1.5 * _quality_score(item, data_type)
            + 1.0 * _activity_score(item)
        )

    # --- Filter, Rank, Deduplicate ---

    def _within_cutoff(item: dict) -> bool:
        if cutoff is None:
            return True
        for field in ("created_at", "timestamp"):
            ts_str = item.get(field, "")
            if ts_str:
                try:
                    return _parse_ts(ts_str) >= cutoff
                except (ValueError, TypeError):
                    continue
        return True

    def _filter_and_rank(items: list[dict], data_type: str) -> list[tuple[float, dict]]:
        scored: list[tuple[float, dict]] = []
        seen_ids: set[str] = set()
        for item in items:
            item_id = item.get("id", "")
            if item_id and item_id in seen_ids:
                continue
            if item_id:
                seen_ids.add(item_id)
            if not _within_cutoff(item):
                continue
            if has_filter and _filter_score(item) == 0.0:
                continue
            score = _composite_score(item, data_type)
            scored.append((score, item))
        # Sort by score descending, then timestamp descending
        scored.sort(
            key=lambda s: (
                -s[0],
                -(
                    _parse_ts(
                        s[1].get("timestamp", s[1].get("created_at", ""))
                        or "1970-01-01T00:00:00Z"
                    ).timestamp()
                ),
            )
        )
        return scored

    # --- Contention Detection ---

    _conflict_outcomes = {
        frozenset({"revised", "pending"}),
        frozenset({"revised", "accepted"}),
        frozenset({"revised", "successful"}),
    }

    def _detect_contention(
        ranked_items: list[tuple[float, dict]], data_type: str
    ) -> list[dict]:
        contentions: list[dict] = []
        seen_pairs: set[frozenset[str]] = set()
        items = [item for _, item in ranked_items]
        if data_type == "decisions":
            # Group by shared tags — flag divergent outcomes
            tag_groups: dict[str, list[dict]] = {}
            for item in items:
                for t in item.get("tags", []):
                    tag_groups.setdefault(t.lower(), []).append(item)
            for tag, group in tag_groups.items():
                if len(group) < 2:
                    continue
                outcomes = [d.get("outcome", "") for d in group]
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        pair = frozenset({outcomes[i], outcomes[j]})
                        if pair not in _conflict_outcomes:
                            continue
                        id_pair = frozenset(
                            {group[i].get("id", ""), group[j].get("id", "")}
                        )
                        if id_pair in seen_pairs:
                            continue
                        seen_pairs.add(id_pair)
                        contentions.append(
                            {
                                "tag": tag,
                                "a": group[i].get("id", ""),
                                "b": group[j].get("id", ""),
                                "outcomes": f"{outcomes[i]} vs {outcomes[j]}",
                            }
                        )
        elif data_type == "patterns":
            # Same category + shared tags = contention
            cat_groups: dict[str, list[dict]] = {}
            for item in items:
                cat = item.get("category", "").lower()
                if cat:
                    cat_groups.setdefault(cat, []).append(item)
            for cat, group in cat_groups.items():
                if len(group) < 2:
                    continue
                for i in range(len(group)):
                    tags_i = set(t.lower() for t in group[i].get("tags", []))
                    for j in range(i + 1, len(group)):
                        tags_j = set(t.lower() for t in group[j].get("tags", []))
                        shared = tags_i & tags_j
                        if not shared:
                            continue
                        id_pair = frozenset(
                            {group[i].get("id", ""), group[j].get("id", "")}
                        )
                        if id_pair in seen_pairs:
                            continue
                        seen_pairs.add(id_pair)
                        contentions.append(
                            {
                                "tag": cat,
                                "a": group[i].get("id", ""),
                                "b": group[j].get("id", ""),
                                "outcomes": "different solutions",
                            }
                        )
        return contentions

    # Gather and rank each section
    all_patterns = _filter_and_rank(lore.patterns(), "patterns")
    all_anti = _filter_and_rank(lore.anti_patterns(), "anti_patterns")
    all_decisions = _filter_and_rank(lore.decisions(), "decisions")
    all_goals = _filter_and_rank(lore.active_goals(), "goals")

    # Detect contentions before budget filling
    contentions = _detect_contention(all_decisions, "decisions") + _detect_contention(
        all_patterns, "patterns"
    )

    # Build output within budget
    used = 0
    truncated = False

    def _add_items(scored_items, extract_fn):
        nonlocal used, truncated
        result = []
        for score, item in scored_items:
            entry = extract_fn(item)
            entry["_score"] = round(score, 2)
            cost = _estimate_tokens(json.dumps(entry))
            if used + cost > budget:
                truncated = True
                break
            used += cost
            result.append(entry)
        return result

    out_patterns = _add_items(
        all_patterns,
        lambda p: {
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "solution": p.get("solution", ""),
            "confidence": p.get("confidence", 0),
        },
    )

    out_anti = _add_items(
        all_anti,
        lambda a: {
            "id": a.get("id", ""),
            "name": a.get("name", ""),
            "risk": a.get("risk", ""),
            "fix": a.get("fix", ""),
        },
    )

    out_decisions = _add_items(
        all_decisions,
        lambda d: {
            "id": d.get("id", ""),
            "decision": d.get("title", "") or d.get("decision", ""),
            "rationale": d.get("rationale", ""),
            "outcome": d.get("outcome", ""),
        },
    )

    out_goals = _add_items(
        all_goals,
        lambda g: {
            "id": g.get("id", ""),
            "name": g.get("name", ""),
            "status": g.get("status", ""),
            "success_criteria": [
                sc.get("description", sc) if isinstance(sc, dict) else sc
                for sc in g.get("success_criteria", [])
            ],
        },
    )

    return {
        "patterns": out_patterns,
        "anti_patterns": out_anti,
        "decisions": out_decisions,
        "goals": out_goals,
        "contentions": contentions,
        "filters_applied": {
            "tags": tags or [],
            "project": project or "",
            "since_days": since_days,
        },
        "token_estimate": used,
        "truncated": truncated,
    }


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
    friction hotspots, command overlap, complexity warnings, undocumented items.
    Returns status indicator (healthy/attention/critical).
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
    refinement_results = refinement()

    # Ecosystem hygiene
    overlap_results = ecosystem_overlap()
    complexity_results = ecosystem_complexity()
    undoc_results = undocumented()

    # Determine status
    has_critical_triggers = any(t["count"] >= 5 for t in trigger_results)
    has_blind_spots = blind_spot_results["blind_spot_count"] > 0
    has_overlap = len(overlap_results) > 0
    has_complexity = len(complexity_results) > 0
    has_undocumented = (
        undoc_results["decision_count"] + undoc_results["pattern_count"] > 5
    )
    refinement_total = (
        refinement_results["cluster_count"]
        + refinement_results["chain_count"]
        + refinement_results["aging_count"]
    )

    if has_blind_spots or has_critical_triggers:
        status_val = "critical"
    elif (
        stale_results["stale_count"] > 0
        or len(trigger_results) > 0
        or has_overlap
        or has_complexity
        or has_undocumented
        or refinement_total > 0
    ):
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
            "overlap_count": len(overlap_results),
            "complexity_warnings": len(complexity_results),
            "undocumented_decisions": undoc_results["decision_count"],
            "undocumented_patterns": undoc_results["pattern_count"],
            "refinement_count": refinement_total,
        },
        "triggers": trigger_results,
        "stale_observations": stale_results["stale_observations"],
        "blind_spots": blind_spot_results["orphaned_failures"],
        "friction": friction_results,
        "refinement": refinement_results,
        "overlap": overlap_results,
        "complexity": complexity_results,
        "undocumented": undoc_results,
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
            results.append(
                {
                    "error_type": et,
                    "count": len(entries),
                }
            )

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
    from failure context.
    """
    fails = lore.failures()
    reg = lore.registry()

    if not fails:
        return []

    deps = reg.get("dependencies", {})
    project_names = set(deps.keys())

    boundary_failures: dict[str, list[dict]] = {}
    for f in fails:
        # Check if project name appears in failure message or project field
        context_str = f"{f.get('project', '')} {f.get('error_message', '')}"

        boundary = None
        for proj in project_names:
            if proj in context_str:
                boundary = proj
                break

        if boundary:
            boundary_failures.setdefault(boundary, []).append(f)

    results = []
    for boundary, flist in sorted(boundary_failures.items(), key=lambda x: -len(x[1])):
        error_counts = Counter(f.get("error_type", "unknown") for f in flist)
        results.append(
            {
                "boundary": boundary,
                "failure_count": len(flist),
                "error_types": dict(error_counts),
            }
        )

    return results


def blind_spots(threshold: int = 3) -> dict:
    """Failures that recur without a corresponding journal entry.

    Groups failures by error_type, finds those with >= threshold
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
        key = f.get("error_type", "unknown")
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
            error_type = key
            orphaned.append(
                {
                    "error_type": error_type,
                    "count": len(flist),
                    "first_occurrence": first_ts.isoformat(),
                    "latest_occurrence": latest_ts.isoformat(),
                }
            )
            suggestions.append(f"Investigate {error_type} failures")

    return {
        "orphaned_failures": orphaned,
        "blind_spot_count": len(orphaned),
        "suggestions": suggestions,
    }


def refinement(min_cluster: int = 3, stale_days: int = 14) -> dict:
    """Decisions ripe for promotion to patterns.

    Surfaces three signals:
    1. Tag clusters — tags with min_cluster+ decisions but no pattern.
    2. Decision chains — related_decisions forming chains of min_cluster+
       without a corresponding pattern.
    3. Aging decisions — older than stale_days with no outcome or pending.
    """
    decs = lore.decisions()
    pats = lore.patterns()

    # -- Tag clusters --
    # Build searchable text from each pattern
    pattern_text = []
    for p in pats:
        parts = [
            p.get("name", ""),
            p.get("context", ""),
            p.get("problem", ""),
            p.get("category", ""),
        ]
        pattern_text.append(" ".join(parts).lower())
    combined_pattern_text = " ".join(pattern_text)

    # Group decisions by tag
    tag_decisions: dict[str, list[dict]] = {}
    for d in decs:
        for tag in d.get("tags", []):
            if tag:
                tag_decisions.setdefault(tag, []).append(d)

    tag_clusters = []
    for tag, tag_decs in sorted(tag_decisions.items()):
        if len(tag_decs) < min_cluster:
            continue
        if tag.lower() in combined_pattern_text:
            continue
        tag_clusters.append(
            {
                "tag": tag,
                "decision_count": len(tag_decs),
                "decisions": [d.get("id", "?") for d in tag_decs],
                "suggestion": f'lore learn "{tag} pattern" --problem "what it solves"',
            }
        )

    # -- Decision chains --
    # Build adjacency from related_decisions
    adjacency: dict[str, set[str]] = {}
    dec_by_id: dict[str, dict] = {}
    for d in decs:
        did = d.get("id", "")
        if not did:
            continue
        dec_by_id[did] = d
        adjacency.setdefault(did, set())
        for rel in d.get("related_decisions", []):
            if rel:
                adjacency.setdefault(did, set()).add(rel)
                adjacency.setdefault(rel, set()).add(did)

    # Find connected components via BFS
    visited: set[str] = set()
    components: list[list[str]] = []
    for node in adjacency:
        if node in visited:
            continue
        component = []
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    # Check if any pattern shares tags with the chain
    pattern_tags = set()
    for p in pats:
        cat = p.get("category", "")
        if cat:
            pattern_tags.add(cat.lower())

    decision_chains = []
    for comp in components:
        if len(comp) < min_cluster:
            continue
        # Collect tags from all decisions in the chain
        chain_tags = set()
        for did in comp:
            d = dec_by_id.get(did, {})
            for tag in d.get("tags", []):
                if tag:
                    chain_tags.add(tag.lower())
        # Skip if a pattern already covers this chain's tags
        if chain_tags & pattern_tags:
            continue
        # Determine topic from the first decision with a title
        root = comp[0]
        topic = dec_by_id.get(root, {}).get("title", "") or dec_by_id.get(root, {}).get(
            "decision", ""
        )
        decision_chains.append(
            {
                "root": root,
                "chain_size": len(comp),
                "decisions": sorted(comp),
                "topic": topic,
                "suggestion": (
                    f"Consolidate {len(comp)} related decisions into a pattern"
                ),
            }
        )

    # -- Aging decisions --
    threshold = timedelta(days=stale_days)
    now = _now()
    aging = []
    for d in decs:
        outcome = d.get("outcome", "")
        if outcome and outcome != "pending":
            continue
        try:
            ts = _parse_ts(d.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        age = now - ts
        if age > threshold:
            aging.append(
                {
                    "id": d.get("id", "?"),
                    "decision": d.get("title", "") or d.get("decision", ""),
                    "timestamp": d.get("timestamp", "")[:10],
                    "age_days": age.days,
                    "outcome": outcome or "none",
                }
            )

    aging.sort(key=lambda a: -a["age_days"])

    # -- Suggestions --
    suggestions = []
    for tc in tag_clusters:
        suggestions.append(
            f"Consolidate {tc['decision_count']} {tc['tag']} decisions into a pattern"
        )
    for dc in decision_chains:
        suggestions.append(dc["suggestion"])
    for a in aging[:3]:
        suggestions.append(f'Resolve or close {a["id"]}: "{a["decision"]}"')

    return {
        "tag_clusters": tag_clusters,
        "decision_chains": decision_chains,
        "aging": aging,
        "cluster_count": len(tag_clusters),
        "chain_count": len(decision_chains),
        "aging_count": len(aging),
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


# --- Ecosystem Hygiene ---


def _parse_claude_md_commands(content: str, project: str) -> list[str]:
    """Extract command names from CLAUDE.md.

    Handles two formats:
    1. Code blocks: `project command args`
    2. Table rows: `| `project command` |`
    """
    import re

    commands = set()

    # Pattern 1: Code blocks with project commands
    # Match lines starting with the project name
    for match in re.finditer(rf"^{re.escape(project)}\s+(\w+)", content, re.MULTILINE):
        cmd = match.group(1)
        if cmd and not cmd.startswith("-"):
            commands.add(cmd)

    # Pattern 2: Table rows with backtick-wrapped commands
    for match in re.finditer(
        rf"\|\s*`{re.escape(project)}\s+(\w+)[^`]*`\s*\|", content
    ):
        cmd = match.group(1)
        if cmd and not cmd.startswith("-"):
            commands.add(cmd)

    return sorted(commands)


def _read_project_commands(project: str) -> list[str]:
    """Read commands from a project's CLAUDE.md."""
    import os
    from pathlib import Path

    dev_dir = Path(os.environ.get("DEV_DIR", Path.home() / "dev"))
    claude_md = dev_dir / project / "CLAUDE.md"

    if not claude_md.exists():
        return []

    try:
        content = claude_md.read_text()
        return _parse_claude_md_commands(content, project)
    except (OSError, IOError):
        return []


def ecosystem_overlap() -> list[dict]:
    """Commands that may confuse users across projects.

    Scans CLAUDE.md files for command tables and flags:
    - Commands with identical names in different projects
    """
    projects = lore.projects()
    if not projects:
        return []

    # Collect commands per project
    project_commands: dict[str, list[str]] = {}
    for proj in projects:
        cmds = _read_project_commands(proj)
        if cmds:
            project_commands[proj] = cmds

    # Find overlaps
    command_to_projects: dict[str, list[str]] = {}
    for proj, cmds in project_commands.items():
        for cmd in cmds:
            command_to_projects.setdefault(cmd, []).append(proj)

    results = []
    for cmd, projs in sorted(command_to_projects.items()):
        if len(projs) > 1:
            results.append(
                {
                    "command": cmd,
                    "projects": sorted(projs),
                    "issue": "same name in multiple projects",
                }
            )

    return results


def ecosystem_complexity(
    max_commands: int = 10,
    max_options: int = 5,
) -> list[dict]:
    """Projects with high cognitive load.

    Flags projects exceeding thresholds for command count.
    """
    projects = lore.projects()
    if not projects:
        return []

    results = []
    for proj in projects:
        cmds = _read_project_commands(proj)
        if len(cmds) > max_commands:
            results.append(
                {
                    "project": proj,
                    "command_count": len(cmds),
                    "threshold": max_commands,
                    "issue": f"exceeds {max_commands} commands",
                }
            )

    return results


def undocumented() -> dict:
    """Decisions and patterns lacking rationale.

    Returns dict with:
      decisions: decisions without rationale field
      patterns: patterns without problem or context fields
      decision_count: count of undocumented decisions
      pattern_count: count of undocumented patterns
    """
    decs = lore.decisions()
    pats = lore.patterns()

    undoc_decisions = []
    for d in decs:
        if not d.get("rationale"):
            undoc_decisions.append(
                {
                    "id": d.get("id", "?"),
                    "decision": d.get("decision", "")[:60],
                    "timestamp": d.get("timestamp", "")[:10],
                }
            )

    undoc_patterns = []
    for p in pats:
        missing = []
        if not p.get("problem"):
            missing.append("problem")
        if not p.get("context"):
            missing.append("context")
        if missing:
            undoc_patterns.append(
                {
                    "id": p.get("id", "?"),
                    "name": p.get("name", ""),
                    "missing": missing,
                }
            )

    return {
        "decisions": undoc_decisions,
        "patterns": undoc_patterns,
        "decision_count": len(undoc_decisions),
        "pattern_count": len(undoc_patterns),
    }
