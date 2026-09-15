"""Read from SpecTrace's database.

With DATABASE_URL set, Praxis reads the shared SpecTrace Postgres over
psycopg; queries there fail loudly, because setting the URL asserts the
database exists. Without it, Praxis reads the local db.sqlite3, and an absent
file yields empty results, because Praxis runs without SpecTrace. Either way a
query against a reachable database raises on a moved table or column. Callers
that tolerate an unmigrated or unreachable database gate on db_available().

SQLite location: ~/dev/forge/spec-trace/spectrace/db.sqlite3
"""

import os
import sqlite3

DB_PATH = os.path.expanduser("~/dev/forge/spec-trace/spectrace/db.sqlite3")


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def _to_postgres(sql: str) -> str:
    """Rewrite sqlite3 qmark placeholders to psycopg format placeholders."""
    return sql.replace("?", "%s")


def _require_psycopg():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg isn't installed. "
            "Install the spectrace extra: pip install -e .[spectrace]"
        ) from exc
    return psycopg


def _postgres_query(url: str, sql: str, params: tuple) -> list[dict]:
    """Run a query against the shared Postgres. Raises on any failure."""
    psycopg = _require_psycopg()
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
        return conn.execute(_to_postgres(sql), params).fetchall()


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against SpecTrace's DB.

    Returns an empty list when no DATABASE_URL is set and the SQLite file is
    absent. Raises when the database is present and the query fails.
    """
    url = _database_url()
    if url:
        return _postgres_query(url, sql, params)
    if not os.path.exists(DB_PATH):
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    """Run a query expecting a single row. Returns None when it yields no rows."""
    rows = _query(sql, params)
    return rows[0] if rows else None


def _table_exists(table: str) -> bool:
    """Check whether a table exists in the DB."""
    row = _query_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return row is not None


def db_available() -> bool:
    """True if the SpecTrace DB is reachable and has the requirements table."""
    url = _database_url()
    if url:
        psycopg = _require_psycopg()

        try:
            row = _postgres_query(
                url, "SELECT to_regclass('requirements_requirement') AS name", ()
            )
        except psycopg.OperationalError:
            return False
        return bool(row and row[0]["name"])
    if not os.path.exists(DB_PATH):
        return False
    return _table_exists("requirements_requirement")


def fetch_tasks() -> list[dict]:
    """Fetch all tasks from the SpecTrace database."""
    return _query(
        "SELECT external_id, title, status, claimed_by_id FROM requirements_agenttask"
    )


def coverage_summary() -> dict | None:
    """Coverage counts grouped by verification_status.

    Returns {passing, failing, untested, total} or None if unavailable.
    """
    if not db_available():
        return None
    rows = _query(
        "SELECT verification_status, COUNT(*) as cnt "
        "FROM requirements_requirement "
        "GROUP BY verification_status"
    )
    if not rows:
        return None
    counts = {r["verification_status"]: r["cnt"] for r in rows}
    return {
        "passing": counts.get("passing", 0),
        "failing": counts.get("failing", 0),
        "untested": counts.get("untested", 0),
        "total": sum(counts.values()),
    }


def orphan_requirements() -> list[dict]:
    """Active leaf requirements with no test links.

    Leaf = numchild=0. Orphan = no rows in testrequirementlink.
    """
    return _query(
        "SELECT r.id, r.external_id, r.title, r.risk_level, "
        "  r.verification_status "
        "FROM requirements_requirement r "
        "LEFT JOIN requirements_testrequirementlink trl "
        "  ON trl.requirement_id = r.id "
        "WHERE r.numchild = 0 "
        "  AND r.status != 'draft' "
        "  AND trl.id IS NULL "
        "ORDER BY CASE r.risk_level "
        "  WHEN 'critical' THEN 0 "
        "  WHEN 'high' THEN 1 "
        "  WHEN 'medium' THEN 2 "
        "  WHEN 'low' THEN 3 "
        "  ELSE 4 END, r.external_id"
    )


def stale_links() -> list[dict]:
    """Test links whose test_nodeid isn't in the latest test run's results."""
    # Find the latest test run
    latest = _query_one(
        "SELECT id FROM requirements_testrun ORDER BY imported_at DESC LIMIT 1"
    )
    if not latest:
        return []
    return _query(
        "SELECT trl.id, trl.test_nodeid, trl.requirement_id, "
        "  trl.last_status, r.external_id AS req_external_id "
        "FROM requirements_testrequirementlink trl "
        "JOIN requirements_requirement r ON r.id = trl.requirement_id "
        "WHERE trl.test_nodeid NOT IN ("
        "  SELECT DISTINCT test_nodeid "
        "  FROM requirements_testresult "
        "  WHERE test_run_id = ?"
        ") "
        "ORDER BY trl.test_nodeid",
        (latest["id"],),
    )


def high_risk_issues() -> list[dict]:
    """Critical/high risk requirements with test link and failure counts."""
    return _query(
        "SELECT r.id, r.external_id, r.title, r.risk_level, "
        "  r.verification_status, "
        "  COUNT(trl.id) AS link_count, "
        "  SUM(CASE WHEN trl.last_status = 'failed' THEN 1 ELSE 0 END) "
        "    AS failing_count "
        "FROM requirements_requirement r "
        "LEFT JOIN requirements_testrequirementlink trl "
        "  ON trl.requirement_id = r.id "
        "WHERE r.risk_level IN ('critical', 'high') "
        "GROUP BY r.id "
        "ORDER BY CASE r.risk_level "
        "  WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, "
        "  failing_count DESC"
    )


def latest_test_run() -> dict | None:
    """Most recent test run metadata with pass/fail counts."""
    run = _query_one(
        "SELECT id, imported_at, source_file, git_sha, git_branch "
        "FROM requirements_testrun "
        "ORDER BY imported_at DESC LIMIT 1"
    )
    if not run:
        return None
    counts = _query_one(
        "SELECT "
        "  COUNT(*) AS total, "
        "  SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed, "
        "  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed, "
        "  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors, "
        "  SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped "
        "FROM requirements_testresult WHERE test_run_id = ?",
        (run["id"],),
    )
    run.update(counts or {})
    return run


def integration_risks() -> list[dict]:
    """Tasks sharing requirements or with dependent requirements.

    Returns two risk levels:
    - HIGH: in-flight tasks sharing a requirement
    - MEDIUM: in-flight tasks where one's requirement depends on another's
    """
    in_flight = (
        "'unclaimed','claimed','in_progress','ready_for_review','changes_requested'"
    )

    # HIGH: tasks sharing a requirement
    high = _query(
        "SELECT r.external_id AS req_id, r.title AS req_title, "
        "  t1.external_id AS task_a, t2.external_id AS task_b "
        "FROM requirements_agenttask_requirements ar1 "
        "JOIN requirements_agenttask_requirements ar2 "
        "  ON ar1.requirement_id = ar2.requirement_id "
        "  AND ar1.agenttask_id < ar2.agenttask_id "
        "JOIN requirements_agenttask t1 ON t1.id = ar1.agenttask_id "
        "JOIN requirements_agenttask t2 ON t2.id = ar2.agenttask_id "
        "JOIN requirements_requirement r ON r.id = ar1.requirement_id "
        f"WHERE t1.status IN ({in_flight}) AND t2.status IN ({in_flight})"
    )

    # MEDIUM: tasks whose requirements have a dependency relationship
    medium = _query(
        "SELECT rd.from_requirement_id, rd.to_requirement_id, "
        "  r1.external_id AS req_a, r2.external_id AS req_b, "
        "  t1.external_id AS task_a, t2.external_id AS task_b "
        "FROM requirements_requirement_depends_on rd "
        "JOIN requirements_requirement r1 "
        "  ON r1.id = rd.from_requirement_id "
        "JOIN requirements_requirement r2 "
        "  ON r2.id = rd.to_requirement_id "
        "JOIN requirements_agenttask_requirements ar1 "
        "  ON ar1.requirement_id = r1.id "
        "JOIN requirements_agenttask_requirements ar2 "
        "  ON ar2.requirement_id = r2.id "
        "JOIN requirements_agenttask t1 ON t1.id = ar1.agenttask_id "
        "JOIN requirements_agenttask t2 ON t2.id = ar2.agenttask_id "
        f"WHERE t1.status IN ({in_flight}) AND t2.status IN ({in_flight}) "
        "  AND t1.id != t2.id"
    )

    risks = []
    for row in high:
        risks.append({**row, "level": "HIGH", "reason": "shared requirement"})
    for row in medium:
        risks.append({**row, "level": "MEDIUM", "reason": "dependent requirements"})
    return risks
