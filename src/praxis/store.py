"""Lineage Store: read the same files that lineage.sh writes.

Praxis reads directly from Lineage's filesystem. Write operations delegate
to lineage.sh via subprocess -- the shell CLI remains authoritative.

Paths match the real Lineage layout:
  journal/data/decisions.jsonl   Append-only decision log
  inbox/data/observations.jsonl  Raw observation staging
  patterns/data/patterns.yaml    Learned patterns (YAML)
  graph/data/graph.json          Knowledge graph
"""

import json
import subprocess
from pathlib import Path

from . import config, schema


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    """Read all lines from a JSONL file."""
    if not path.exists():
        return []
    entries = []
    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append(
                        {"_parse_error": True, "_line": line_num, "_raw": line}
                    )
    return entries


def _read_json(path: Path) -> dict:
    """Read a single JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def _read_yaml_via_yq(path: Path) -> dict:
    """Read YAML by shelling out to yq, parse JSON result.

    Keeps Praxis stdlib-only -- no PyYAML dependency.
    Matches how lore-cli.sh reads its own YAML.
    """
    if not path.exists():
        return {}
    result = subprocess.run(
        ["yq", "-o=json", ".", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yq failed on {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Public API: Read
# ---------------------------------------------------------------------------

def read_journal() -> list[dict]:
    """Read the full decision journal."""
    path = config.LINEAGE_DIR / "journal/data/decisions.jsonl"
    entries = _read_jsonl(path)
    for entry in entries:
        if "_parse_error" not in entry:
            errors = schema.validate_decision(entry)
            if errors:
                entry["_validation_errors"] = errors
    return entries


def read_inbox() -> list[dict]:
    """Read the inbox observations."""
    path = config.LINEAGE_DIR / "inbox/data/observations.jsonl"
    entries = _read_jsonl(path)
    for entry in entries:
        if "_parse_error" not in entry:
            errors = schema.validate_observation(entry)
            if errors:
                entry["_validation_errors"] = errors
    return entries


def read_patterns() -> list[dict]:
    """Read patterns from YAML via yq."""
    path = config.LINEAGE_DIR / "patterns/data/patterns.yaml"
    data = _read_yaml_via_yq(path)
    patterns = data.get("patterns", [])
    if not isinstance(patterns, list):
        return []
    for pat in patterns:
        if isinstance(pat, dict):
            errors = schema.validate_pattern(pat)
            if errors:
                pat["_validation_errors"] = errors
    return patterns


def read_graph() -> dict:
    """Read the knowledge graph."""
    path = config.LINEAGE_DIR / "graph/data/graph.json"
    if not path.exists():
        return {"nodes": {}, "edges": []}
    return _read_json(path)


def read_mission(mission_id: str) -> dict:
    """Read a mission from Neo's active missions directory."""
    missions_dir = config.NEO_DIR / "missions/active"
    # Direct match by filename
    direct = missions_dir / f"{mission_id}.yaml"
    if direct.exists():
        data = _read_yaml_via_yq(direct)
        errors = schema.validate_mission(data)
        if errors:
            data["_validation_errors"] = errors
        return data

    # Search by metadata.id inside YAML files
    for path in missions_dir.glob("*.yaml"):
        data = _read_yaml_via_yq(path)
        meta = data.get("metadata", {})
        if isinstance(meta, dict) and meta.get("id") == mission_id:
            errors = schema.validate_mission(data)
            if errors:
                data["_validation_errors"] = errors
            return data

    raise FileNotFoundError(f"Mission not found: {mission_id}")


# ---------------------------------------------------------------------------
# Public API: Write (delegates to lineage.sh)
# ---------------------------------------------------------------------------

def _run_lineage(*args: str) -> subprocess.CompletedProcess:
    """Call lineage.sh with the given arguments."""
    return subprocess.run(
        [config.LINEAGE_CLI, *args],
        capture_output=True,
        text=True,
    )


def observe(text: str, source: str = "praxis", tags: str = "") -> str:
    """Append a raw observation to the Lineage inbox."""
    cmd = [text, "--source", source]
    if tags:
        cmd.extend(["--tags", tags])
    result = _run_lineage("observe", *cmd)
    if result.returncode != 0:
        raise RuntimeError(f"lineage observe failed: {result.stderr.strip()}")
    return result.stdout.strip()


def remember(text: str, rationale: str, tags: str = "") -> str:
    """Record a decision in the Lineage journal."""
    cmd = [text, "--rationale", rationale]
    if tags:
        cmd.extend(["--tags", tags])
    result = _run_lineage("remember", *cmd)
    if result.returncode != 0:
        raise RuntimeError(f"lineage remember failed: {result.stderr.strip()}")
    return result.stdout.strip()


def learn(text: str, context: str = "", solution: str = "") -> str:
    """Capture a pattern in Lineage."""
    cmd = [text]
    if context:
        cmd.extend(["--context", context])
    if solution:
        cmd.extend(["--solution", solution])
    result = _run_lineage("learn", *cmd)
    if result.returncode != 0:
        raise RuntimeError(f"lineage learn failed: {result.stderr.strip()}")
    return result.stdout.strip()


def resume(session_id: str = "") -> str:
    """Resume from a previous Lineage session."""
    cmd = ["resume"]
    if session_id:
        cmd.append(session_id)
    result = _run_lineage(*cmd)
    if result.returncode != 0:
        raise RuntimeError(f"lineage resume failed: {result.stderr.strip()}")
    return result.stdout.strip()


def lineage_search(query: str) -> str:
    """Run lineage search and return raw output."""
    result = _run_lineage("search", query)
    if result.returncode != 0:
        raise RuntimeError(f"lineage search failed: {result.stderr.strip()}")
    return result.stdout.strip()


def lineage_context(project: str) -> str:
    """Run lineage context for a project."""
    result = _run_lineage("context", project)
    if result.returncode != 0:
        raise RuntimeError(
            f"lineage context failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()
