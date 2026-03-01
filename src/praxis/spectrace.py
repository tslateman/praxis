"""Read from SpecTrace's SQLite database.

Praxis reads directly from SpecTrace's db.sqlite3. Returns empty results
when the database doesn't exist or tables are missing.

DB location: ~/dev/forge/spec-trace/spectrace/db.sqlite3
"""

import os
import sqlite3

DB_PATH = os.path.expanduser("~/dev/forge/spec-trace/spectrace/db.sqlite3")


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against SpecTrace's DB. Returns empty list on any error."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
    except sqlite3.Error:
        return []


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    """Run a query expecting a single row. Returns None on any error."""
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
    """True if SpecTrace DB exists and has the requirements table."""
    if not os.path.exists(DB_PATH):
        return False
    return _table_exists("requirements_requirement")


def fetch_tasks() -> list[dict]:
    """Fetch all tasks from the SpecTrace SQLite database."""
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
