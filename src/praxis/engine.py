"""Orchestration engine: delegates to Neo shell scripts for state changes,
reads files directly in Python for validation and context assembly.

Design: read in Python (adds validation), write via shell (delegates authority).
"""

import json
import subprocess

from . import config
from . import store
from . import registry


def sync(mirror_dir: str = "") -> str:
    """Sync ~/.mirror notes into Lineage inbox via Neo's sync.sh."""
    cmd = [config.NEO_SYNC]
    if mirror_dir:
        cmd.extend(["--mirror-dir", mirror_dir])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"sync.sh failed: {result.stderr.strip()}")
    return result.stdout.strip()


def promote(observation_id: str, target_type: str, **kwargs: str) -> str:
    """Promote an inbox observation via Neo's promote.sh.

    target_type: "decision" or "pattern"
    kwargs: rationale, context, solution (passed as flags)
    """
    cmd = [config.NEO_PROMOTE, observation_id, target_type]
    for key, value in kwargs.items():
        if value:
            cmd.extend([f"--{key}", value])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"promote.sh failed: {result.stderr.strip()}")
    return result.stdout.strip()


def start(mission_id: str) -> dict:
    """Hydrate mission context by reading files directly.

    Combines mission YAML (via Neo), Lineage patterns, and Lore context
    into a single dict. Falls back to Neo's start.sh if direct read fails.
    """
    # Try direct Python read first (adds validation)
    try:
        mission = store.read_mission(mission_id)
    except FileNotFoundError:
        # Fall back to Neo's start.sh
        result = subprocess.run(
            [config.NEO_START, mission_id],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"start.sh failed: {result.stderr.strip()}"
            )
        return json.loads(result.stdout)

    # Extract objective for pattern search
    spec = mission.get("spec", {})
    objective = spec.get("objective", "")
    project = mission.get("metadata", {}).get("labels", {}).get(
        "project", "unknown"
    )

    # Query patterns
    patterns = []
    if objective:
        from . import search as search_mod

        pattern_hits = search_mod.search_patterns(objective)
        patterns = [hit["data"] for hit in pattern_hits[:5]]

    # Query Lore context
    lore_context = {}
    if project != "unknown":
        try:
            lore_context = registry.context(project)
        except Exception:
            pass

    # Query Lineage context
    lineage_context = ""
    try:
        lineage_context = store.lineage_context(project)
    except Exception:
        pass

    return {
        "mission": mission,
        "patterns": patterns,
        "lore": lore_context,
        "lineage_context": lineage_context,
    }


def context(project: str) -> dict:
    """Combined Lineage + Lore context for a project."""
    result = {"project": project}

    # Lore context
    try:
        result["lore"] = registry.context(project)
    except Exception:
        result["lore"] = {}

    # Lineage context
    try:
        result["lineage"] = store.lineage_context(project)
    except Exception:
        result["lineage"] = ""

    return result


def status() -> dict:
    """Session and mission status."""
    result = {}

    # Current inbox count
    inbox = store.read_inbox()
    raw = [e for e in inbox if e.get("status") == "raw"]
    result["inbox"] = {"total": len(inbox), "raw": len(raw)}

    # Journal entry count
    journal = store.read_journal()
    result["journal"] = {"entries": len(journal)}

    # Pattern count
    patterns = store.read_patterns()
    result["patterns"] = {"count": len(patterns)}

    return result
