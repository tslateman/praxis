"""Structured failure journals -- the Compounding Wisdom engine.

Every failure gets a coroner's report in Lineage's failures directory.
Over time, these reports reveal whether you need better tools, clearer
plans, or different approaches.

Adapted from praxis-rdx/failure.py. Key changes:
- JSONL instead of YAML (stdlib-only, matches Lineage conventions)
- Single append-only file instead of one file per failure
- Writes to ~/dev/lineage/failures/data/failures.jsonl

Error type vocabulary:
    UserDeny    -- Human said no.
    HardDeny    -- Denylist blocked it.
    NonZeroExit -- Command ran but failed.
    Timeout     -- Command hung.
    ToolError   -- Tool crashed or returned garbage.
    LogicError  -- Output was wrong (caught by eval, not crash).
"""

import json
from datetime import datetime, timezone

from praxis.config import FAILURES_DIR, FAILURES_FILE

ERROR_TYPES = frozenset(
    ["UserDeny", "HardDeny", "NonZeroExit", "Timeout", "ToolError", "LogicError"]
)

_counter = 0


def log_failure(
    mission_id: str,
    step_id: int,
    tool: str,
    error_type: str,
    error_message: str,
    context: dict | None = None,
    correction: str = "",
) -> dict:
    """Write a failure report to the JSONL journal.

    Returns the written report dict.
    """
    global _counter
    _counter += 1

    if error_type not in ERROR_TYPES:
        raise ValueError(
            f"Unknown error_type '{error_type}'. "
            f"Valid types: {', '.join(sorted(ERROR_TYPES))}"
        )

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    fail_id = f"fail-{date_str}-{_counter:03d}"

    report = {
        "id": fail_id,
        "timestamp": now.isoformat(),
        "mission": mission_id,
        "step": step_id,
        "tool": tool,
        "error_type": error_type,
        "error_message": error_message,
    }

    if context:
        report["context_snippet"] = _truncate_context(context)

    if correction:
        report["correction_attempted"] = correction

    FAILURES_DIR.mkdir(parents=True, exist_ok=True)

    with open(FAILURES_FILE, "a") as f:
        f.write(json.dumps(report) + "\n")

    return report


def read_failures() -> list[dict]:
    """Read all failure reports from the JSONL file."""
    if not FAILURES_FILE.exists():
        return []

    results = []
    with open(FAILURES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def _truncate_context(context: dict, max_chars: int = 500) -> str:
    """Keep context readable."""
    raw = str(context)
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "... [truncated]"
