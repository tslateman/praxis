"""Emit fleet dispatch payloads to Blueprint's inbox."""

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

INBOX_DIR = Path(
    os.environ.get(
        "BLUEPRINT_INBOX",
        str(Path.home() / ".local/share/blueprint/inbox/fleet"),
    )
)


def emit_payload(team: str, tasks: list[dict], runtime: str = "local") -> Path:
    """Write a fleet dispatch YAML to the inbox directory.

    Args:
        team: Shipyard team name
        tasks: List of task dicts, each with name, title, agent_type,
               and optionally scope_in, done_when, depends_on
        runtime: Shipyard runtime (default: local)

    Returns:
        Path to the written dispatch file
    """
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{ts}_{team}.yaml"
    path = INBOX_DIR / filename
    payload = {"team": team, "runtime": runtime, "tasks": tasks}
    path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))
    return path
