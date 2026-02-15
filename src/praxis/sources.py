"""Read data from ecosystem projects.

Each reader resolves paths from environment variables with sensible
defaults. Missing files return empty lists with a warning to stderr.
"""

import json
import sys
from pathlib import Path

from praxis.config import (
    INBOX_FILE,
    JOURNAL_FILE,
    MIRROR_DIR,
    NEO_LOGS_DIR,
)


def _read_jsonl(path: Path, source_name: str) -> list[dict]:
    """Read a JSONL file, warning on missing files."""
    if not path.exists():
        print(f"Warning: {source_name} not found at {path}", file=sys.stderr)
        return []
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def read_journal() -> list[dict]:
    """Read decision entries from Lore's journal."""
    return _read_jsonl(JOURNAL_FILE, "journal")


def read_inbox() -> list[dict]:
    """Read observation entries from Lore's inbox."""
    return _read_jsonl(INBOX_FILE, "inbox")


def read_neo_logs(log_name: str) -> list[dict]:
    """Read a Neo log file, parsing timestamp/action/details.

    Log format: 2026-02-14T17:37:27Z sync: ingested test-observation.md -> ...
    """
    path = NEO_LOGS_DIR / f"{log_name}.log"
    if not path.exists():
        print(f"Warning: Neo log not found at {path}", file=sys.stderr)
        return []
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Split on first space for timestamp, then ": " for action/details
            parts = line.split(" ", 1)
            if len(parts) < 2:
                continue
            timestamp = parts[0]
            remainder = parts[1]
            action_parts = remainder.split(": ", 1)
            action = action_parts[0]
            details = action_parts[1] if len(action_parts) > 1 else ""
            results.append({
                "timestamp": timestamp,
                "action": action,
                "details": details,
            })
    return results


def read_mirror_yaml(filename: str) -> list[dict]:
    """Read a YAML file from the Mirror directory.

    Requires PyYAML. Returns empty list if PyYAML is not installed.
    """
    try:
        import yaml
    except ImportError:
        print(
            "Warning: PyYAML not installed, cannot read Mirror files",
            file=sys.stderr,
        )
        return []

    path = MIRROR_DIR / filename
    if not path.exists():
        print(f"Warning: Mirror file not found at {path}", file=sys.stderr)
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []
