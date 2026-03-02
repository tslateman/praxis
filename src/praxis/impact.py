"""Impact graph reader — blast radius across the ecosystem.

Assembles an in-memory graph from spectrace-map.yaml files,
git co-change inference, and contract snapshots. No Django dependency.

Project roots from PRAXIS_PROJECT_ROOTS env (colon-separated key=path pairs)
or defaults to ~/dev/{lore,praxis,geordi,forge/spec-trace,shipyard}.
"""

import json
import logging
import os
import re
import subprocess
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default project roots
_DEFAULT_ROOTS = {
    "lore": Path.home() / "dev/lore",
    "praxis": Path.home() / "dev/praxis",
    "geordi": Path.home() / "dev/geordi",
    "spectrace": Path.home() / "dev/forge/spec-trace",
    "shipyard": Path.home() / "dev/shipyard",
}

GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:\-~^@{}]*$")


def _project_roots() -> dict[str, Path]:
    """Get project roots from env or defaults."""
    env = os.environ.get("PRAXIS_PROJECT_ROOTS")
    if env:
        roots = {}
        for pair in env.split(":"):
            if "=" in pair:
                name, path = pair.split("=", 1)
                roots[name.strip()] = Path(path.strip())
        return roots
    return dict(_DEFAULT_ROOTS)


def _validate_ref(ref: str) -> None:
    """Validate a git ref for safety."""
    if not ref:
        raise ValueError("Git ref cannot be empty")
    if len(ref) > 256:
        raise ValueError("Git ref too long")
    if not GIT_REF_PATTERN.match(ref):
        raise ValueError("Invalid git ref format")
    if ref.startswith("-"):
        raise ValueError("Git ref cannot start with a hyphen")


# --- Map Reader ---


def read_spectrace_map(
    project: str, roots: Optional[dict[str, Path]] = None
) -> list[dict]:
    """Parse spectrace-map.yaml for a project, return module mappings.

    Returns list of dicts: [{module, requirement, project}]
    Missing file returns empty list.
    """
    all_roots = roots or _project_roots()
    root = all_roots.get(project)
    if not root:
        return []

    map_file = root / "spectrace-map.yaml"
    if not map_file.exists():
        return []

    try:
        with open(map_file) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return []

    if not isinstance(data, dict):
        return []

    mappings = []
    modules = data.get("modules", {})
    if not isinstance(modules, dict):
        return []

    for module_path, info in modules.items():
        if not isinstance(info, dict):
            continue
        for req_id in info.get("requirements", []):
            if isinstance(req_id, str):
                mappings.append(
                    {
                        "module": module_path,
                        "requirement": req_id,
                        "project": project,
                    }
                )
    return mappings


# --- Contract Reader ---


def read_contract_snapshot(
    project: str, roots: Optional[dict[str, Path]] = None
) -> dict:
    """Parse contract.snapshot.json for a project, return surfaces.

    Returns dict with project, version, surfaces.
    Missing file returns empty dict.
    """
    all_roots = roots or _project_roots()
    root = all_roots.get(project)
    if not root:
        return {}

    snap_file = root / "contract.snapshot.json"
    if not snap_file.exists():
        return {}

    try:
        with open(snap_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# --- Git Operations ---


def git_changed_files(
    project: str,
    base: str,
    head: str,
    roots: Optional[dict[str, Path]] = None,
) -> list[str]:
    """Get changed files between two refs in a project repo.

    Returns list of relative file paths. Empty on error.
    """
    _validate_ref(base)
    _validate_ref(head)

    all_roots = roots or _project_roots()
    root = all_roots.get(project)
    if not root or not root.exists():
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []


def git_co_changes(
    project: str,
    min_count: int = 3,
    lookback_days: int = 90,
    roots: Optional[dict[str, Path]] = None,
) -> list[dict]:
    """Get git co-change pairs for a project, enforcing Rule of Three.

    Returns list of dicts: [{file_a, file_b, count, weight}]
    """
    all_roots = roots or _project_roots()
    root = all_roots.get(project)
    if not root or not root.exists():
        return []

    since_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%d"
    )

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--name-only",
                "--pretty=format:%H|%aI",
                f"--since={since_date}",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []

    # Parse commits
    commits: list[tuple[datetime, list[str]]] = []
    current_date: Optional[datetime] = None
    current_files: list[str] = []

    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            parts = line.split("|")
            if len(parts) == 2 and len(parts[0]) == 40:
                if current_date is not None:
                    commits.append((current_date, current_files))
                try:
                    dt = datetime.fromisoformat(parts[1])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    current_date = dt
                    current_files = []
                except ValueError:
                    current_date = None
                    current_files = []
                continue
        if current_date is not None:
            current_files.append(line)

    if current_date is not None:
        commits.append((current_date, current_files))

    # Count co-occurrences
    pair_dates: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for date, files in commits:
        files = sorted(set(files))
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                pair_dates[(files[i], files[j])].append(date)

    # Apply Rule of Three with rolling window
    now = datetime.now(timezone.utc)
    decay_threshold = now - timedelta(days=90)
    results = []

    for (file_a, file_b), dates in pair_dates.items():
        dates.sort()
        max_window = 0
        for d in dates:
            window_start = d - timedelta(days=30)
            count = sum(1 for dd in dates if window_start <= dd <= d)
            max_window = max(max_window, count)

        if max_window < min_count:
            continue

        total = len(dates)
        weight = min(1.0, total / 10)
        if max(dates) < decay_threshold:
            weight *= 0.5

        results.append(
            {
                "file_a": file_a,
                "file_b": file_b,
                "count": total,
                "weight": round(weight, 2),
            }
        )

    return results


# --- Graph Assembly ---


def build_graph(
    base: str,
    head: str,
    projects: Optional[list[str]] = None,
    roots: Optional[dict[str, Path]] = None,
) -> dict:
    """Assemble impact graph and compute blast radius.

    Returns dict with:
      changed_files: {project: [files]}
      blast: {directly_changed, affected_requirements, affected_modules,
              affected_projects, risk_score, risk_level}
      edge_summary: {annotated, inferred, contract}
    """
    all_roots = roots or _project_roots()
    target_projects = projects or list(all_roots.keys())

    # Collect edges from all sources
    annotated: list[tuple[str, str, str, float]] = []  # (src, tgt, project, weight)
    inferred: list[tuple[str, str, str, float]] = []
    contract: list[tuple[str, str, str, float]] = []

    changed_files: dict[str, list[str]] = {}

    for project in target_projects:
        if project not in all_roots:
            continue

        # Changed files
        files = git_changed_files(project, base, head, all_roots)
        if files:
            changed_files[project] = files

        # Annotated edges from spectrace-map.yaml
        mappings = read_spectrace_map(project, all_roots)
        for m in mappings:
            annotated.append((m["module"], m["requirement"], project, 1.0))

        # Inferred edges from git co-change
        co_changes = git_co_changes(project, roots=all_roots)
        for cc in co_changes:
            inferred.append((cc["file_a"], cc["file_b"], project, cc["weight"]))

        # Contract edges
        snap = read_contract_snapshot(project, all_roots)
        if snap:
            for surface_name in snap.get("surfaces", {}):
                contract.append(
                    (f"{project}:{surface_name}", surface_name, project, 0.8)
                )

    # Build adjacency for BFS
    adjacency: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    all_edges = (
        [(s, t, p, w, "annotated") for s, t, p, w in annotated]
        + [(s, t, p, w, "inferred") for s, t, p, w in inferred]
        + [(s, t, p, w, "contract") for s, t, p, w in contract]
    )

    for src, tgt, proj, weight, _kind in all_edges:
        adjacency[src].append((tgt, proj, weight))
        adjacency[tgt].append((src, proj, weight))

    # BFS from all changed files
    all_changed = []
    for proj_files in changed_files.values():
        all_changed.extend(proj_files)

    visited: set[str] = set(all_changed)
    queue: deque[tuple[str, int]] = deque((f, 0) for f in all_changed)
    max_depth = 3

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor, proj, weight in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    # Categorize affected nodes
    affected = visited - set(all_changed)
    requirements = sorted(
        n for n in affected if n.startswith("REQ-") or n.startswith("req-")
    )
    modules = sorted(n for n in affected if "/" in n and not n.startswith("REQ-"))
    projects_hit: set[str] = set()
    for _, _, proj, _, _k in all_edges:
        if proj:
            projects_hit.add(proj)

    # Risk scoring
    mod_signal = min(1.0, len(modules) / 10)
    req_signal = min(1.0, len(requirements) / 10)
    proj_signal = min(1.0, len(projects_hit) / 5)
    cross_signal = min(1.0, len(changed_files) / 5)

    risk_score = round(
        0.3 * mod_signal + 0.3 * req_signal + 0.2 * proj_signal + 0.2 * cross_signal,
        2,
    )

    if risk_score >= 0.75:
        risk_level = "critical"
    elif risk_score >= 0.5:
        risk_level = "high"
    elif risk_score >= 0.25:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "changed_files": changed_files,
        "blast": {
            "directly_changed": all_changed,
            "affected_requirements": requirements,
            "affected_modules": modules,
            "affected_projects": sorted(projects_hit),
            "risk_score": risk_score,
            "risk_level": risk_level,
        },
        "edge_summary": {
            "annotated": len(annotated),
            "inferred": len(inferred),
            "contract": len(contract),
        },
    }
