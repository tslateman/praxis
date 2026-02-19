"""Read from Lore's data files.

Praxis reads directly from Lore's JSONL/YAML storage. No subprocess
calls to `lore` CLI — direct file access keeps it fast.

Data locations (relative to LORE_DIR):
  failures/data/failures.jsonl     Failure reports
  inbox/data/observations.jsonl    Raw observations
  journal/data/decisions.jsonl     Decisions with rationale
  intent/data/goals/*.yaml         Goal definitions
  intent/missions/*.yaml           Mission breakdowns
  registry/data/relationships.yaml Project relationships
"""

import json
import os
from pathlib import Path

import yaml

LORE_DIR = Path(os.environ.get("LORE_DIR", Path.home() / "dev/lore"))


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file. Missing file returns empty list."""
    if not path.exists():
        return []
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def _read_yaml(path: Path) -> dict | None:
    """Read a YAML file. Missing file returns None."""
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def _read_yaml_dir(directory: Path) -> list[dict]:
    """Read all YAML files in a directory."""
    if not directory.exists():
        return []
    results = []
    for path in directory.glob("*.yaml"):
        data = _read_yaml(path)
        if data:
            results.append(data)
    return results


# --- Failures ---

def failures() -> list[dict]:
    """Read failure reports."""
    return _read_jsonl(LORE_DIR / "failures" / "data" / "failures.jsonl")


# --- Inbox ---

def observations() -> list[dict]:
    """Read inbox observations."""
    return _read_jsonl(LORE_DIR / "inbox" / "data" / "observations.jsonl")


def raw_observations() -> list[dict]:
    """Read observations with status='raw'."""
    return [o for o in observations() if o.get("status") == "raw"]


# --- Journal ---

def decisions() -> list[dict]:
    """Read journal decisions."""
    return _read_jsonl(LORE_DIR / "journal" / "data" / "decisions.jsonl")


# --- Intent ---

def goals() -> list[dict]:
    """Read all goals."""
    return _read_yaml_dir(LORE_DIR / "intent" / "data" / "goals")


def active_goals() -> list[dict]:
    """Read goals with status='active'."""
    return [g for g in goals() if g.get("status") == "active"]


def missions() -> list[dict]:
    """Read all missions."""
    return _read_yaml_dir(LORE_DIR / "intent" / "missions")


def pending_missions() -> list[dict]:
    """Read missions not yet completed."""
    return [m for m in missions() if m.get("status") not in ("completed", "failed", "cancelled")]


# --- Registry ---

def registry() -> dict:
    """Read project relationships. Returns empty dict if missing."""
    data = _read_yaml(LORE_DIR / "registry" / "data" / "relationships.yaml")
    return data if isinstance(data, dict) else {}


def patterns() -> list[dict]:
    """Read learned patterns."""
    data = _read_yaml(LORE_DIR / "patterns" / "data" / "patterns.yaml")
    if data and isinstance(data.get("patterns"), list):
        return data["patterns"]
    return []


def projects() -> list[str]:
    """List all projects in the registry."""
    reg = registry()
    deps = reg.get("dependencies", {})
    return sorted(deps.keys())
