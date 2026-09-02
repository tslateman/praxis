"""Tests for praxis.spectrace — SpecTrace DB reader."""

import sqlite3

import pytest

from praxis import spectrace


def _create_schema(conn):
    """Create SpecTrace tables matching Django's schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS requirements_requirement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path VARCHAR(255) UNIQUE NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0,
            numchild INTEGER NOT NULL DEFAULT 0,
            external_id VARCHAR(50) UNIQUE NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            priority VARCHAR(20) DEFAULT '',
            status VARCHAR(20) DEFAULT 'draft',
            risk_level VARCHAR(20) DEFAULT 'unclassified',
            verification_method VARCHAR(20) DEFAULT 'unspecified',
            verification_status VARCHAR(20) DEFAULT 'untested',
            slo_status VARCHAR(20) DEFAULT 'not_linked',
            scope TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            component VARCHAR(255) DEFAULT '',
            timing VARCHAR(100) DEFAULT '',
            response TEXT DEFAULT '',
            structure_completeness REAL DEFAULT 0.0,
            source_file VARCHAR(500) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS requirements_testrequirementlink (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_nodeid VARCHAR(500) NOT NULL,
            requirement_id INTEGER NOT NULL REFERENCES requirements_requirement(id),
            last_status VARCHAR(20) DEFAULT 'unknown',
            last_run_at DATETIME,
            needs_review INTEGER DEFAULT 0,
            review_reason VARCHAR(200) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(test_nodeid, requirement_id)
        );

        CREATE TABLE IF NOT EXISTS requirements_testrun (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_file VARCHAR(500) DEFAULT '',
            git_sha VARCHAR(40) DEFAULT '',
            git_branch VARCHAR(200) DEFAULT '',
            ci_job_url VARCHAR(500) DEFAULT '',
            workflow_name VARCHAR(200) DEFAULT '',
            workflow_run_id INTEGER,
            repository VARCHAR(200) DEFAULT '',
            started_at DATETIME,
            finished_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS requirements_testresult (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_nodeid VARCHAR(500) NOT NULL,
            classname VARCHAR(300) DEFAULT '',
            name VARCHAR(200) NOT NULL,
            time REAL DEFAULT 0.0,
            status VARCHAR(20) NOT NULL,
            message TEXT DEFAULT '',
            test_run_id INTEGER NOT NULL REFERENCES requirements_testrun(id)
        );

        CREATE TABLE IF NOT EXISTS requirements_agenttask (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id VARCHAR(100) UNIQUE NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'draft',
            claimed_by_id INTEGER,
            claimed_at DATETIME,
            lease_expires DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS requirements_agenttask_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agenttask_id INTEGER NOT NULL REFERENCES requirements_agenttask(id),
            requirement_id INTEGER NOT NULL REFERENCES requirements_requirement(id)
        );

        CREATE TABLE IF NOT EXISTS requirements_requirement_depends_on (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_requirement_id INTEGER NOT NULL
                REFERENCES requirements_requirement(id),
            to_requirement_id INTEGER NOT NULL
                REFERENCES requirements_requirement(id)
        );
    """)


@pytest.fixture()
def spectrace_db(tmp_path, monkeypatch):
    """Create a SpecTrace DB with test data and patch DB_PATH."""
    db_path = str(tmp_path / "db.sqlite3")
    conn = sqlite3.connect(db_path)
    _create_schema(conn)

    # Requirements: 5 total
    # R-001: passing, critical, has test link
    # R-002: failing, high, has test link
    # R-003: untested, medium, leaf, no test link (orphan)
    # R-004: passing, low, leaf, has test link
    # R-005: untested, critical, leaf, no test link (orphan)
    conn.executemany(
        "INSERT INTO requirements_requirement "
        "(path, depth, numchild, external_id, title, status, risk_level, "
        " verification_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("0001", 1, 0, "R-001", "Auth login", "active", "critical", "passing"),
            ("0002", 1, 0, "R-002", "Auth token refresh", "active", "high", "failing"),
            ("0003", 1, 0, "R-003", "Error display", "active", "medium", "untested"),
            ("0004", 1, 0, "R-004", "Log rotation", "active", "low", "passing"),
            ("0005", 1, 0, "R-005", "Failover", "active", "critical", "untested"),
        ],
    )

    # Test links for R-001, R-002, R-004
    conn.executemany(
        "INSERT INTO requirements_testrequirementlink "
        "(test_nodeid, requirement_id, last_status) VALUES (?, ?, ?)",
        [
            ("tests/test_auth.py::test_login", 1, "passed"),
            ("tests/test_auth.py::test_refresh", 2, "failed"),
            ("tests/test_logs.py::test_rotation", 4, "passed"),
            # Stale link: test_nodeid not in latest run
            ("tests/test_old.py::test_removed", 1, "passed"),
        ],
    )

    # Test run + results
    conn.execute(
        "INSERT INTO requirements_testrun "
        "(id, source_file, git_sha, git_branch) "
        "VALUES (1, 'results.xml', 'abc123', 'main')"
    )
    conn.executemany(
        "INSERT INTO requirements_testresult "
        "(test_nodeid, name, status, test_run_id) VALUES (?, ?, ?, 1)",
        [
            ("tests/test_auth.py::test_login", "test_login", "passed"),
            ("tests/test_auth.py::test_refresh", "test_refresh", "failed"),
            ("tests/test_logs.py::test_rotation", "test_rotation", "passed"),
        ],
    )

    # Agent tasks (both in-flight, sharing R-001)
    conn.executemany(
        "INSERT INTO requirements_agenttask "
        "(id, external_id, title, status) VALUES (?, ?, ?, ?)",
        [
            (1, "T-001", "Fix auth", "in_progress"),
            (2, "T-002", "Add monitoring", "in_progress"),
            (3, "T-003", "Done task", "merged"),
        ],
    )
    # Both tasks share R-001
    conn.executemany(
        "INSERT INTO requirements_agenttask_requirements "
        "(agenttask_id, requirement_id) VALUES (?, ?)",
        [(1, 1), (2, 1), (1, 2)],
    )

    # Requirement dependency: R-002 depends on R-001
    conn.execute(
        "INSERT INTO requirements_requirement_depends_on "
        "(from_requirement_id, to_requirement_id) VALUES (2, 1)"
    )

    conn.commit()
    conn.close()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(spectrace, "DB_PATH", db_path)
    return db_path


@pytest.fixture()
def missing_db(tmp_path, monkeypatch):
    """Point DB_PATH at a nonexistent file."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(spectrace, "DB_PATH", str(tmp_path / "nope.db"))


@pytest.fixture()
def empty_db(tmp_path, monkeypatch):
    """DB exists but has no SpecTrace tables."""
    db_path = str(tmp_path / "empty.db")
    sqlite3.connect(db_path).close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(spectrace, "DB_PATH", db_path)


@pytest.fixture()
def renamed_column_db(tmp_path, monkeypatch):
    """SpecTrace DB whose agenttask.claimed_by_id column carries a new name."""
    db_path = str(tmp_path / "renamed_column.sqlite3")
    conn = sqlite3.connect(db_path)
    _create_schema(conn)
    conn.execute(
        "ALTER TABLE requirements_agenttask RENAME COLUMN claimed_by_id TO assignee_id"
    )
    conn.commit()
    conn.close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(spectrace, "DB_PATH", db_path)
    return db_path


class TestDbAvailable:
    def test_true_with_tables(self, spectrace_db):
        assert spectrace.db_available() is True

    def test_false_missing_db(self, missing_db):
        assert spectrace.db_available() is False

    def test_false_empty_db(self, empty_db):
        assert spectrace.db_available() is False


class TestFetchTasks:
    def test_returns_tasks(self, spectrace_db):
        result = spectrace.fetch_tasks()
        assert len(result) == 3
        ids = [t["external_id"] for t in result]
        assert "T-001" in ids

    def test_missing_db_returns_empty(self, missing_db):
        assert spectrace.fetch_tasks() == []


class TestCoverageSummary:
    def test_counts(self, spectrace_db):
        result = spectrace.coverage_summary()
        assert result is not None
        assert result["passing"] == 2
        assert result["failing"] == 1
        assert result["untested"] == 2
        assert result["total"] == 5

    def test_missing_db_returns_none(self, missing_db):
        assert spectrace.coverage_summary() is None

    def test_empty_db_returns_none(self, empty_db):
        assert spectrace.coverage_summary() is None


class TestOrphanRequirements:
    def test_finds_orphans(self, spectrace_db):
        result = spectrace.orphan_requirements()
        ids = [r["external_id"] for r in result]
        assert "R-003" in ids
        assert "R-005" in ids
        # R-001 has a test link, not an orphan
        assert "R-001" not in ids

    def test_sorted_by_risk(self, spectrace_db):
        result = spectrace.orphan_requirements()
        # R-005 (critical) should come before R-003 (medium)
        ids = [r["external_id"] for r in result]
        assert ids.index("R-005") < ids.index("R-003")

    def test_missing_db_returns_empty(self, missing_db):
        assert spectrace.orphan_requirements() == []


class TestStaleLinks:
    def test_finds_stale(self, spectrace_db):
        result = spectrace.stale_links()
        nodeids = [r["test_nodeid"] for r in result]
        assert "tests/test_old.py::test_removed" in nodeids

    def test_excludes_current(self, spectrace_db):
        result = spectrace.stale_links()
        nodeids = [r["test_nodeid"] for r in result]
        assert "tests/test_auth.py::test_login" not in nodeids

    def test_missing_db_returns_empty(self, missing_db):
        assert spectrace.stale_links() == []


class TestHighRiskIssues:
    def test_finds_critical_and_high(self, spectrace_db):
        result = spectrace.high_risk_issues()
        ids = [r["external_id"] for r in result]
        assert "R-001" in ids  # critical
        assert "R-002" in ids  # high
        # R-003 is medium, excluded
        assert "R-003" not in ids

    def test_failing_count(self, spectrace_db):
        result = spectrace.high_risk_issues()
        r002 = next(r for r in result if r["external_id"] == "R-002")
        assert r002["failing_count"] == 1

    def test_missing_db_returns_empty(self, missing_db):
        assert spectrace.high_risk_issues() == []


class TestLatestTestRun:
    def test_returns_run_metadata(self, spectrace_db):
        result = spectrace.latest_test_run()
        assert result is not None
        assert result["git_branch"] == "main"
        assert result["git_sha"] == "abc123"
        assert result["passed"] == 2
        assert result["failed"] == 1

    def test_missing_db_returns_none(self, missing_db):
        assert spectrace.latest_test_run() is None


class TestIntegrationRisks:
    def test_finds_shared_requirement(self, spectrace_db):
        result = spectrace.integration_risks()
        high = [r for r in result if r["level"] == "HIGH"]
        assert len(high) >= 1
        # T-001 and T-002 share R-001
        pair = high[0]
        tasks = {pair["task_a"], pair["task_b"]}
        assert tasks == {"T-001", "T-002"}

    def test_finds_dependent_requirement(self, spectrace_db):
        result = spectrace.integration_risks()
        medium = [r for r in result if r["level"] == "MEDIUM"]
        # T-001 has R-002, which depends on R-001 (T-002 has R-001)
        assert len(medium) >= 1

    def test_missing_db_returns_empty(self, missing_db):
        assert spectrace.integration_risks() == []


class TestPostgresDispatch:
    def test_url_routes_queries_to_postgres(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://example/spectrace")
        captured = {}

        def fake_postgres_query(url, sql, params):
            captured["url"] = url
            return [{"external_id": "T-PG"}]

        monkeypatch.setattr(spectrace, "_postgres_query", fake_postgres_query)
        result = spectrace.fetch_tasks()
        assert result == [{"external_id": "T-PG"}]
        assert captured["url"] == "postgres://example/spectrace"

    def test_no_url_stays_on_sqlite(self, missing_db):
        assert spectrace.fetch_tasks() == []

    def test_placeholders_rewritten_for_postgres(self):
        assert spectrace._to_postgres("SELECT * FROM t WHERE a=? AND b=?") == (
            "SELECT * FROM t WHERE a=%s AND b=%s"
        )


class TestSchemaDrift:
    def test_fetch_tasks__raises_when_table_is_missing(self, empty_db):
        with pytest.raises(sqlite3.OperationalError, match="requirements_agenttask"):
            spectrace.fetch_tasks()

    def test_fetch_tasks__raises_when_column_is_renamed(self, renamed_column_db):
        with pytest.raises(sqlite3.OperationalError, match="claimed_by_id"):
            spectrace.fetch_tasks()
