import os
import sqlite3

DB_PATH = os.path.expanduser("~/dev/forge/spec-trace/spectrace/db.sqlite3")


def fetch_tasks() -> list[dict]:
    """Fetch all tasks from the SpecTrace SQLite database.

    Returns a list of dictionaries with keys:
        - external_id
        - title
        - status
        - claimed_by_id
    """
    if not os.path.exists(DB_PATH):
        return []

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if the table exists first
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='requirements_agenttask'"
            )
            if not cursor.fetchone():
                return []

            cursor.execute(
                "SELECT external_id, title, status, claimed_by_id "
                "FROM requirements_agenttask"
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
    except sqlite3.Error:
        return []
