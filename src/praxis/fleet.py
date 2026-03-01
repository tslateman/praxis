"""Read from fleet.db — agent fleet management database.

Praxis reads directly from fleet.db SQLite. Returns empty results
when the database doesn't exist.

DB location: FLEET_DB env var or ~/dev/fleets/m2/fleet.db
"""

import os
import sqlite3
from pathlib import Path

FLEET_DB_PATH = Path(os.environ.get("FLEET_DB", Path.home() / "dev/fleets/m2/fleet.db"))


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against fleet.db. Returns empty list on any error."""
    if not FLEET_DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(str(FLEET_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []


def agents() -> list[dict]:
    """Active agents."""
    return _query("SELECT * FROM agents WHERE is_active = 1")


def tasks() -> list[dict]:
    """All tasks."""
    return _query("SELECT * FROM tasks")


def active_tasks() -> list[dict]:
    """Non-terminal tasks (everything except merged/abandoned)."""
    return _query("SELECT * FROM tasks WHERE status NOT IN ('merged', 'abandoned')")


def events(limit: int = 50) -> list[dict]:
    """Recent tool-call events."""
    return _query("SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,))


def failures() -> list[dict]:
    """All fleet failures, newest first."""
    return _query("SELECT * FROM failures ORDER BY created_at DESC")


def token_summary() -> list[dict]:
    """Token usage aggregated by agent and model."""
    return _query("SELECT * FROM token_summary")


def invariant_violations() -> list[dict]:
    """All invariant violations (INV-A through INV-H)."""
    return _query("SELECT * FROM inv_all_violations")


def expired_leases() -> list[dict]:
    """Tasks with expired leases that need reclaiming."""
    return _query("SELECT * FROM expired_leases")


def merge_queue() -> list[dict]:
    """Tasks awaiting merge: approved or ready_for_review."""
    return _query(
        "SELECT * FROM tasks "
        "WHERE status IN ('approved', 'ready_for_review') "
        "ORDER BY updated_at"
    )


def rule_of_three_violations() -> list[dict]:
    """Failure signatures appearing 3+ times in the last hour per agent."""
    return _query("SELECT * FROM rule_of_three_violations")


def blind_spots() -> list[dict]:
    """Recurring failures with no intervention in 7 days."""
    return _query("SELECT * FROM blind_spots")


def scope_overlap() -> list[dict]:
    """Active task pairs sharing files in scope_in."""
    return _query("SELECT * FROM scope_overlap")
