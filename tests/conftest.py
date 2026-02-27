"""Shared fixtures for Praxis tests.

Creates a temporary Lore directory tree with realistic JSONL/YAML data.
Sets LORE_DIR so praxis.lore reads from the fixture data.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml


def _now():
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _days_ago(n: int) -> str:
    return _iso(_now() - timedelta(days=n))


# --- JSONL / YAML helpers ---


def _write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


# --- Fixtures ---


@pytest.fixture()
def lore_dir(tmp_path, monkeypatch):
    """Create a populated Lore directory tree and patch LORE_DIR.

    Returns the tmp_path root so tests can add/modify files as needed.
    """
    # Mock spectrace by default
    monkeypatch.setattr("praxis.spectrace.fetch_tasks", lambda: [])

    # -- Failures --
    _write_jsonl(
        tmp_path / "failures" / "data" / "failures.jsonl",
        [
            {
                "id": "fail-001",
                "error_type": "Timeout",
                "error_message": "Connection timed out to API",
                "project": "lore",
                "timestamp": _days_ago(2),
            },
            {
                "id": "fail-002",
                "error_type": "Timeout",
                "error_message": "Build step timed out",
                "project": "lore",
                "timestamp": _days_ago(3),
            },
            {
                "id": "fail-003",
                "error_type": "Timeout",
                "error_message": "Another timeout",
                "project": "lore",
                "timestamp": _days_ago(1),
            },
            {
                "id": "fail-004",
                "error_type": "NonZeroExit",
                "error_message": "pytest returned 1",
                "project": "bach",
                "timestamp": _days_ago(1),
            },
            {
                "id": "fail-005",
                "error_type": "ParseError",
                "error_message": "Invalid YAML",
                "project": "lore",
                "timestamp": _days_ago(30),
            },
        ],
    )

    # -- Observations --
    _write_jsonl(
        tmp_path / "inbox" / "data" / "observations.jsonl",
        [
            {
                "id": "obs-001",
                "content": "Lore CLI response times increasing",
                "status": "raw",
                "timestamp": _days_ago(10),
            },
            {
                "id": "obs-002",
                "content": "Bach workers idle on weekends",
                "status": "raw",
                "timestamp": _days_ago(2),
            },
            {
                "id": "obs-003",
                "content": "Registry schema settled",
                "status": "processed",
                "timestamp": _days_ago(15),
            },
            {
                "id": "obs-004",
                "content": "Old stale observation from weeks ago",
                "status": "raw",
                "timestamp": _days_ago(20),
            },
        ],
    )

    # -- Decisions --
    _write_jsonl(
        tmp_path / "journal" / "data" / "decisions.jsonl",
        [
            {
                "id": "dec-001",
                "title": "Use JSONL for append-heavy data",
                "decision": "Use JSONL for append-heavy data",
                "rationale": "Append-only writes, easy line-by-line reads",
                "outcome": "accepted",
                "tags": ["storage", "architecture"],
                "timestamp": _days_ago(5),
            },
            {
                "id": "dec-002",
                "title": "Archive Neo and Ralph",
                "decision": "Archive Neo and Ralph",
                "rationale": "Claude Code native teams replace custom orchestration",
                "outcome": "successful",
                "tags": ["architecture", "ecosystem"],
                "related_decisions": ["dec-003"],
                "timestamp": _days_ago(3),
            },
            {
                "id": "dec-003",
                "title": "Adopt Claude Code teams",
                "decision": "Adopt Claude Code teams",
                "rationale": "",
                "outcome": "pending",
                "tags": ["architecture"],
                "related_decisions": ["dec-002"],
                "timestamp": _days_ago(20),
            },
            {
                "id": "dec-004",
                "title": "Old unresolved decision",
                "decision": "Old unresolved decision",
                "rationale": "Was going to do this",
                "outcome": "",
                "tags": ["cleanup"],
                "timestamp": _days_ago(30),
            },
            {
                "id": "dec-005",
                "title": "Revised storage approach",
                "decision": "Revised storage approach",
                "rationale": "Original plan had perf issues",
                "outcome": "revised",
                "tags": ["storage"],
                "timestamp": _days_ago(4),
            },
        ],
    )

    # -- Goals --
    goals_dir = tmp_path / "intent" / "data" / "goals"
    _write_yaml(
        goals_dir / "goal-001.yaml",
        {
            "id": "goal-001",
            "name": "Ship Lore v2",
            "status": "active",
            "priority": "high",
            "tags": ["lore", "architecture"],
            "projects": ["lore"],
            "success_criteria": [
                {"description": "All readers migrated"},
                {"description": "Tests passing"},
            ],
        },
    )
    _write_yaml(
        goals_dir / "goal-002.yaml",
        {
            "id": "goal-002",
            "name": "Praxis test coverage",
            "status": "active",
            "priority": "medium",
            "tags": ["praxis", "testing"],
            "projects": ["praxis"],
            "success_criteria": ["80% coverage"],
        },
    )
    _write_yaml(
        goals_dir / "goal-003.yaml",
        {
            "id": "goal-003",
            "name": "Old archived goal",
            "status": "archived",
            "priority": "low",
            "tags": ["cleanup"],
            "projects": [],
        },
    )

    # -- Registry --
    _write_yaml(
        tmp_path / "registry" / "data" / "relationships.yaml",
        {
            "dependencies": {
                "lore": {"depends_on": []},
                "praxis": {"depends_on": ["lore"]},
                "bach": {"depends_on": ["lore"]},
                "council": {"depends_on": ["lore"]},
            }
        },
    )

    # -- Patterns --
    _write_yaml(
        tmp_path / "patterns" / "data" / "patterns.yaml",
        {
            "patterns": [
                {
                    "id": "pat-001",
                    "name": "TTL caching for file reads",
                    "category": "performance",
                    "problem": "Repeated file reads within a session waste I/O",
                    "context": "Any reader that hits Lore data files",
                    "solution": "Wrap readers with TTL cache, default 30s",
                    "confidence": 0.85,
                    "validations": 3,
                    "spec_quality": 0.7,
                    "tags": ["caching", "performance"],
                    "projects": ["praxis"],
                    "created_at": _days_ago(10),
                },
                {
                    "id": "pat-002",
                    "name": "Conventional commit prefixes",
                    "category": "workflow",
                    "problem": "",
                    "context": "Git history readability",
                    "solution": "Use feat:, fix:, docs:, refactor:, test:, chore:",
                    "confidence": 0.9,
                    "validations": 8,
                    "spec_quality": 0.5,
                    "tags": ["git", "workflow"],
                    "projects": [],
                    "created_at": _days_ago(30),
                },
            ],
            "anti_patterns": [
                {
                    "id": "anti-001",
                    "name": "Subprocess calls for data reads",
                    "severity": "high",
                    "risk": "Slow, fragile, hard to test",
                    "fix": "Read files directly",
                    "tags": ["performance"],
                    "created_at": _days_ago(5),
                },
                {
                    "id": "anti-002",
                    "name": "Uncached repeated reads",
                    "severity": "medium",
                    "risk": "Redundant I/O on every call",
                    "fix": "Add TTL caching",
                    "tags": ["caching"],
                    "created_at": _days_ago(8),
                },
            ],
        },
    )

    # Patch the module-level LORE_DIR and clear cache
    import praxis.lore as lore_mod

    monkeypatch.setattr(lore_mod, "LORE_DIR", tmp_path)
    lore_mod.cache_clear()

    yield tmp_path

    # Clean up cache after test
    lore_mod.cache_clear()


@pytest.fixture()
def empty_lore_dir(tmp_path, monkeypatch):
    """A Lore directory with no data files at all."""
    import praxis.lore as lore_mod

    monkeypatch.setattr(lore_mod, "LORE_DIR", tmp_path)
    monkeypatch.setattr("praxis.spectrace.fetch_tasks", lambda: [])
    lore_mod.cache_clear()

    yield tmp_path

    lore_mod.cache_clear()
