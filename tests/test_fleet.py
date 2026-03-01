"""Tests for praxis.fleet — fleet.db reader."""

import sqlite3
from pathlib import Path

import pytest

from praxis import fleet


@pytest.fixture()
def fleet_db(tmp_path, monkeypatch):
    """Create a fleet.db with test data and patch FLEET_DB_PATH."""
    db_path = tmp_path / "fleet.db"
    conn = sqlite3.connect(str(db_path))

    # Read and execute the schema
    schema_path = Path.home() / "dev/fleets/m2/src/schema/fleet.sql"
    conn.executescript(schema_path.read_text())

    # Insert test data
    conn.execute(
        "INSERT INTO teams (team_id, name, status, created_at, updated_at) "
        "VALUES ('team-1', 'Alpha', 'active', datetime('now'), datetime('now'))"
    )
    now = "datetime('now')"
    conn.execute(
        "INSERT INTO agents "
        "(agent_id, team_id, role, model, registered_at) "
        f"VALUES ('agent-1', 'team-1', 'implementer', "
        f"'claude-sonnet-4-6', {now})"
    )
    conn.execute(
        "INSERT INTO agents "
        "(agent_id, team_id, role, model, is_active, "
        "registered_at) "
        f"VALUES ('agent-2', 'team-1', 'reviewer', "
        f"'claude-sonnet-4-6', 0, {now})"
    )
    conn.execute(
        "INSERT INTO tasks "
        "(task_id, team_id, status, title, branch, "
        "created_at, updated_at) "
        f"VALUES ('task-1', 'team-1', 'draft', "
        f"'Build widget', NULL, {now}, {now})"
    )
    # Transition draft → unclaimed
    conn.execute(
        "UPDATE tasks SET status = 'unclaimed', updated_at = datetime('now') "
        "WHERE task_id = 'task-1'"
    )
    conn.execute(
        "INSERT INTO tasks "
        "(task_id, team_id, status, title, branch, "
        "created_at, updated_at) "
        f"VALUES ('task-2', 'team-1', 'draft', "
        f"'Add tests', 'feat/tests', {now}, {now})"
    )
    # Transition draft → unclaimed → claimed → in_progress
    conn.execute(
        "UPDATE tasks SET status = 'unclaimed', updated_at = datetime('now') "
        "WHERE task_id = 'task-2'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'claimed', claimed_by = 'agent-1', "
        "claimed_at = datetime('now'), lease_expires = datetime('now', '+30 minutes'), "
        "updated_at = datetime('now') WHERE task_id = 'task-2'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') "
        "WHERE task_id = 'task-2'"
    )
    conn.execute(
        "INSERT INTO tasks "
        "(task_id, team_id, status, title, "
        "created_at, updated_at) "
        f"VALUES ('task-3', 'team-1', 'draft', "
        f"'Merged task', {now}, {now})"
    )
    # draft → unclaimed → claimed → in_progress
    # → ready_for_review → approved → merged
    conn.execute(
        "UPDATE tasks SET status = 'unclaimed', updated_at = datetime('now') "
        "WHERE task_id = 'task-3'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'claimed', claimed_by = 'agent-1', "
        "claimed_at = datetime('now'), lease_expires = datetime('now', '+30 minutes'), "
        "updated_at = datetime('now') WHERE task_id = 'task-3'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') "
        "WHERE task_id = 'task-3'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'ready_for_review', updated_at = datetime('now') "
        "WHERE task_id = 'task-3'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'approved', updated_at = datetime('now') "
        "WHERE task_id = 'task-3'"
    )
    conn.execute(
        "UPDATE tasks SET status = 'merged', updated_at = datetime('now') "
        "WHERE task_id = 'task-3'"
    )

    # Events
    conn.execute(
        "INSERT INTO events (agent_id, tool_name, summary, created_at) "
        "VALUES ('agent-1', 'Bash', 'Run tests', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO events (agent_id, tool_name, summary, created_at) "
        "VALUES ('agent-1', 'Edit', 'Edit src/main.ts', datetime('now', '-1 minute'))"
    )

    # Failures
    conn.execute(
        "INSERT INTO failures "
        "(agent_id, task_id, error_type, "
        "error_message, created_at) "
        "VALUES ('agent-1', 'task-2', "
        f"'ValidationFailure', 'Tests failed', {now})"
    )

    conn.commit()
    conn.close()

    monkeypatch.setattr(fleet, "FLEET_DB_PATH", db_path)
    return db_path


@pytest.fixture()
def missing_fleet_db(tmp_path, monkeypatch):
    """Point FLEET_DB_PATH at a nonexistent file."""
    monkeypatch.setattr(fleet, "FLEET_DB_PATH", tmp_path / "nope.db")
    return tmp_path


class TestAgents:
    def test_returns_active_agents(self, fleet_db):
        result = fleet.agents()
        assert len(result) == 1
        assert result[0]["agent_id"] == "agent-1"

    def test_excludes_inactive(self, fleet_db):
        ids = [a["agent_id"] for a in fleet.agents()]
        assert "agent-2" not in ids

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.agents() == []


class TestTasks:
    def test_returns_all_tasks(self, fleet_db):
        result = fleet.tasks()
        assert len(result) == 3

    def test_active_tasks_excludes_terminal(self, fleet_db):
        result = fleet.active_tasks()
        ids = [t["task_id"] for t in result]
        assert "task-1" in ids  # unclaimed
        assert "task-2" in ids  # in_progress
        assert "task-3" not in ids  # merged

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.tasks() == []


class TestEvents:
    def test_returns_events_newest_first(self, fleet_db):
        result = fleet.events()
        assert len(result) == 2
        assert result[0]["tool_name"] == "Bash"  # newest

    def test_respects_limit(self, fleet_db):
        result = fleet.events(limit=1)
        assert len(result) == 1

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.events() == []


class TestFailures:
    def test_returns_failures(self, fleet_db):
        result = fleet.failures()
        assert len(result) == 1
        assert result[0]["error_type"] == "ValidationFailure"

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.failures() == []


class TestMergeQueue:
    def test_empty_when_nothing_ready(self, fleet_db):
        # task-1 is unclaimed, task-2 is in_progress, task-3 is merged
        result = fleet.merge_queue()
        assert len(result) == 0

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.merge_queue() == []


class TestInvariantViolations:
    def test_clean_db_has_no_violations(self, fleet_db):
        result = fleet.invariant_violations()
        assert len(result) == 0

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.invariant_violations() == []


class TestRuleOfThreeViolations:
    def test_clean_db_has_none(self, fleet_db):
        assert fleet.rule_of_three_violations() == []

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.rule_of_three_violations() == []

    def test_detects_repeated_failures(self, fleet_db):
        conn = sqlite3.connect(str(fleet_db))
        for i in range(4):
            conn.execute(
                "INSERT INTO failures "
                "(agent_id, task_id, error_type, error_message, signature, created_at) "
                "VALUES ('agent-1', 'task-2', 'ToolError', 'same error', "
                "'sig-abc', datetime('now'))"
            )
        conn.commit()
        conn.close()
        result = fleet.rule_of_three_violations()
        assert len(result) == 1
        assert result[0]["signature"] == "sig-abc"
        assert result[0]["occurrence_count"] >= 3


class TestBlindSpots:
    def test_clean_db_has_none(self, fleet_db):
        assert fleet.blind_spots() == []

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.blind_spots() == []

    def test_detects_unaddressed_failures(self, fleet_db):
        conn = sqlite3.connect(str(fleet_db))
        for i in range(4):
            conn.execute(
                "INSERT INTO failures "
                "(agent_id, task_id, error_type, error_message, signature, created_at) "
                "VALUES ('agent-1', 'task-2', 'Stall', 'stuck again', "
                "'sig-blind', datetime('now', '-1 hour'))"
            )
        conn.commit()
        conn.close()
        result = fleet.blind_spots()
        assert len(result) >= 1
        sigs = [r.get("signature") for r in result]
        assert "sig-blind" in sigs


class TestScopeOverlap:
    def test_no_overlap_in_fixture(self, fleet_db):
        assert fleet.scope_overlap() == []

    def test_missing_db_returns_empty(self, missing_fleet_db):
        assert fleet.scope_overlap() == []

    def test_detects_shared_files(self, fleet_db):
        conn = sqlite3.connect(str(fleet_db))
        # Create two in_progress tasks with overlapping scope_in
        conn.execute(
            "INSERT INTO tasks "
            "(task_id, team_id, status, title, scope_in, created_at, updated_at) "
            "VALUES ('task-ov-1', 'team-1', 'draft', 'Overlap A', "
            "'[\"src/main.py\", \"src/utils.py\"]', datetime('now'), datetime('now'))"
        )
        conn.execute(
            "UPDATE tasks SET status = 'unclaimed', updated_at = datetime('now') "
            "WHERE task_id = 'task-ov-1'"
        )
        conn.execute(
            "UPDATE tasks SET status = 'claimed', "
            "claimed_by = 'agent-1', claimed_at = datetime('now'), "
            "lease_expires = datetime('now', '+30 minutes'), "
            "updated_at = datetime('now') WHERE task_id = 'task-ov-1'"
        )
        conn.execute(
            "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') "
            "WHERE task_id = 'task-ov-1'"
        )
        conn.execute(
            "INSERT INTO tasks "
            "(task_id, team_id, status, title, scope_in, created_at, updated_at) "
            "VALUES ('task-ov-2', 'team-1', 'draft', 'Overlap B', "
            "'[\"src/main.py\", \"src/other.py\"]', datetime('now'), datetime('now'))"
        )
        conn.execute(
            "UPDATE tasks SET status = 'unclaimed', updated_at = datetime('now') "
            "WHERE task_id = 'task-ov-2'"
        )
        conn.execute(
            "UPDATE tasks SET status = 'claimed', "
            "claimed_by = 'agent-1', claimed_at = datetime('now'), "
            "lease_expires = datetime('now', '+30 minutes'), "
            "updated_at = datetime('now') WHERE task_id = 'task-ov-2'"
        )
        conn.execute(
            "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') "
            "WHERE task_id = 'task-ov-2'"
        )
        conn.commit()
        conn.close()
        result = fleet.scope_overlap()
        assert len(result) >= 1
        files = [r["shared_file"] for r in result]
        assert "src/main.py" in files
