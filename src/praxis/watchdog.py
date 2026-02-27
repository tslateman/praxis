"""Watchdog failure ingest for Tier 0 mechanical monitoring."""

import hashlib
import json
import logging
import re
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from praxis import lore

# Minimal state to persist across runs
STATE_FILE = Path.home() / ".local" / "share" / "praxis" / "watchdog_state.json"

logger = logging.getLogger(__name__)


class FailureEntry(TypedDict):
    timestamp: float
    signature: str
    command: str
    project: str
    exit_code: int


class WatchdogState(TypedDict):
    history: list[FailureEntry]
    reported: dict[str, float]  # signature -> timestamp


def _load_state() -> WatchdogState:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state, starting fresh: {e}")
    return {"history": [], "reported": {}}


def _save_state(state: WatchdogState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _redact_secrets(text: str) -> str:
    """Redact obvious secrets from output before hashing/saving."""
    # Basic redaction: tokens that look like long base64/hex strings
    text = re.sub(r"([A-Za-z0-9_-]{32,})", "<REDACTED>", text)
    # Redact common env var assignments if they leak
    text = re.sub(r"(?i)(password|secret|key|token)=([^\s]+)", r"\1=<REDACTED>", text)
    return text


def _hash_output(stdout: str, stderr: str, exit_code: int) -> str:
    """Create a hash signature of the failure."""
    # We take the last few lines as they usually contain the actual error
    lines = (stdout + "\n" + stderr).strip().splitlines()
    tail = "\n".join(lines[-20:])  # last 20 lines
    content = _redact_secrets(tail).encode("utf-8")

    h = hashlib.sha256()
    h.update(str(exit_code).encode("utf-8"))
    h.update(b"|")
    h.update(content)
    return h.hexdigest()[:12]


def run_watchdog(
    cmd: str,
    project: str,
    window_sec: int,
    threshold: int,
    interval_sec: int,
) -> None:
    """Run the watchdog loop."""
    print(f"Starting watchdog for project '{project}'")
    print(f"Command: {cmd}")
    print(f"Threshold: {threshold} failures in {window_sec}s")
    print(f"Interval: {interval_sec}s")

    args = shlex.split(cmd)

    while True:
        try:
            result = subprocess.run(args, capture_output=True, text=True)
            if result.returncode != 0:
                _handle_failure(cmd, project, result, window_sec, threshold)

            time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("Watchdog stopped.")
            break
        except Exception as e:
            logger.error(f"Watchdog execution error: {e}")
            time.sleep(interval_sec)


def _handle_failure(
    cmd: str,
    project: str,
    result: subprocess.CompletedProcess,
    window_sec: int,
    threshold: int,
) -> None:
    now = time.time()
    sig = _hash_output(result.stdout, result.stderr, result.returncode)

    state = _load_state()
    history = state.get("history", [])
    reported = state.get("reported", {})

    # Filter out old history
    history = [h for h in history if now - h["timestamp"] <= window_sec]

    # Add new failure
    history.append(
        {
            "timestamp": now,
            "signature": sig,
            "command": cmd,
            "project": project,
            "exit_code": result.returncode,
        }
    )

    # Count occurrences of this signature
    recent_count = sum(1 for h in history if h["signature"] == sig)

    if recent_count >= threshold:
        last_reported = reported.get(sig, 0)
        # Only report if we haven't reported THIS signature in the current window
        if now - last_reported > window_sec:
            _report_to_lore(cmd, project, sig, result)
            reported[sig] = now
            # Do not remove reported from history so we don't double count
            # if we tweak logic

    state["history"] = history
    state["reported"] = reported
    _save_state(state)


def _report_to_lore(
    cmd: str, project: str, sig: str, result: subprocess.CompletedProcess
) -> None:
    print(f"\n[Watchdog] Triggering Rule of Three for {cmd} (sig: {sig})")

    summary = f"Watchdog: repeated failures for `{cmd}` in project `{project}`"

    # Combine output and redact
    out = _redact_secrets((result.stdout + "\n" + result.stderr).strip())
    # Truncate for lore
    if len(out) > 1000:
        out = out[-1000:] + "\n... (truncated)"

    details = (
        f"[{project}] {summary}\n\n"
        f"Signature: {sig}\n"
        f"Exit Code: {result.returncode}\n\n"
        f"Output Snippet:\n```\n{out}\n```"
    )

    lore.fail(error_type="NonZeroExit", message=details, tool="watchdog")


def report_status() -> None:
    """Print a summary of the watchdog state."""
    state = _load_state()
    history = state.get("history", [])
    reported = state.get("reported", {})

    print("Watchdog Status Report")
    print("======================")

    if not history:
        print("No recent failures tracked.")
        return

    # Group by signature
    from collections import Counter

    sig_counts = Counter(h["signature"] for h in history)

    # Get details for each sig
    details = {}
    for h in history:
        if h["signature"] not in details:
            details[h["signature"]] = h

    for sig, count in sig_counts.most_common():
        d = details[sig]
        dt = datetime.fromtimestamp(d["timestamp"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%SZ"
        )
        is_reported = " (REPORTED)" if sig in reported else ""
        print(f"\nSignature: {sig}{is_reported}")
        print(f"  Project:   {d['project']}")
        print(f"  Command:   {d['command']}")
        print(f"  Failures:  {count} in current window")
        print(f"  Last Seen: {dt}")
