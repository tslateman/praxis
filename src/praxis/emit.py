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


def emit_from_triggers(triggers: list[dict], threshold: int = 5) -> list[Path]:
    """Convert Rule of Three trigger signals into fleet dispatch payloads.

    Each trigger above the threshold becomes a single-task dispatch:
    one builder scoped to the project where the failure recurs.

    Args:
        triggers: Output from synthesis.triggers() — list of dicts
                  with error_type, count, projects, etc.
        threshold: Minimum failure count to emit (default: 5)

    Returns:
        List of paths to written dispatch files
    """
    paths = []
    for t in triggers:
        if t.get("count", 0) < threshold:
            continue

        error_type = t.get("error_type", "unknown")
        projects = t.get("projects", [])
        project = projects[0] if projects else "unknown"

        team_name = f"fix-{error_type.lower().replace(' ', '-')}"
        tasks = [
            {
                "name": "fix",
                "title": f"Fix recurring {error_type} in {project}",
                "agent_type": "builder",
                "scope_in": [f"{project}/**"] if project != "unknown" else [],
                "done_when": [f"{error_type} no longer recurs"],
            }
        ]

        path = emit_payload(team_name, tasks)
        paths.append(path)

    return paths
