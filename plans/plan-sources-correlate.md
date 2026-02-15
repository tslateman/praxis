# Plan: Data Access Layer and Cross-Source Commands

## Status

**Status:** Complete -- implemented and verified 2026-02-15

## Context

Praxis analyzes failure journals stored in a single JSONL file. The ecosystem
has five more data sources that nobody correlates: Lore journal (55 decisions),
Lore inbox (3 observations), Lore registry (project relationships), Neo logs
(sync/promote events), and Mirror captures (judgments, patterns).

This plan adds a data access layer (`sources.py`) and two cross-source commands
(`correlate`, `stale`). It is Phase 1 of the Praxis Analysis initiative. See
`~/dev/council/initiatives/praxis-analysis.md` for the full initiative.

**Relationship to Lore and mnemo:**

Lore now owns failure writes natively (`lore fail`, `lore failures`,
`lore triggers` in `failures/lib/failures.sh`). Praxis's Python readers for
failures duplicate what Lore's shell lib does. The Python path remains useful
because `correlate` needs to join two reader outputs programmatically --
shell-native joins are awkward.

[mnemo](https://github.com/Pilan-AI/mnemo) is a local session search tool that
indexes JSONL natively. A Lore indexer for mnemo would make all of Lore's data
searchable via keyword similarity and auto-inject relevant history into agent
prompts via a UserPromptSubmit hook. The tools answer different questions:

| Tool               | Question                                      | Method                |
| ------------------ | --------------------------------------------- | --------------------- |
| mnemo              | "What past work relates to this prompt?"      | Text search + BM25    |
| Praxis `correlate` | "What decisions were near this failure?"      | Timestamp-window join |
| Praxis `stale`     | "What observations are aging without action?" | Status + age filter   |
| Praxis `triggers`  | "Which error types are systemic?"             | Count threshold       |

`sources.py` is the piece mnemo could eventually replace. If mnemo adds a Lore
indexer with a programmatic API, Praxis could query mnemo instead of reading
files directly. Build `sources.py` now; swap if mnemo provides a better path.

**Existing code to study:**

- `src/praxis/config.py` -- Path resolution pattern (environment variable with
  default). Reference: `~/dev/praxis/src/praxis/config.py:10-12`
- `src/praxis/failure.py:83-94` -- `read_failures()` JSONL reader. The new
  readers follow this same pattern.
- `src/praxis/analysis.py:14-32` -- `summarize()` shows how analysis functions
  consume readers. New analysis functions compose across multiple readers.
- `bin/praxis:87-120` -- CLI subcommand pattern with `--json` flag support.

**Data formats (verified from live files):**

Lore journal (`~/dev/lore/journal/data/decisions.jsonl`):

```json
{
  "id": "dec-56153ab9",
  "timestamp": "2026-02-10T03:48:04Z",
  "session_id": "session-07ed6a2f",
  "decision": "Use lib/store.sh for storage logic",
  "rationale": "...",
  "type": "implementation",
  "tags": []
}
```

Lore inbox (`~/dev/lore/inbox/data/observations.jsonl`):

```json
{
  "id": "obs-76a62b2b",
  "timestamp": "2026-02-14T17:37:27Z",
  "source": "test-observation.md",
  "content": "Vector search fails on large datasets",
  "status": "raw",
  "tags": ["mirror", "sync"]
}
```

Lore failures (`~/dev/lore/failures/data/failures.jsonl`):

```json
{
  "id": "fail-2026-02-14-001",
  "timestamp": "...",
  "mission": "...",
  "step": 1,
  "tool": "shell",
  "error_type": "NonZeroExit",
  "error_message": "..."
}
```

Lore registry (`~/dev/lore/registry/data/relationships.yaml`):

```yaml
dependencies:
  bach:
    depends_on:
      - project: flow
        type: runtime
        reason: Receives tasks via TASK_CONTRACT
```

Neo logs (`~/dev/neo/logs/sync.log`, `promote.log`):

```text
2026-02-14T17:37:27Z sync: ingested test-observation.md -> archive/...
2026-02-14T17:37:40Z promote: obs-76a62b2b -> decision (rationale: Needs investigation)
```

## What to Do

### 1. Create `src/praxis/sources.py`

One reader function per data source. Each returns a list of dicts. Follow the
`read_failures()` pattern from `failure.py:83-94`.

```python
"""Read data from ecosystem projects.

Each reader resolves paths from environment variables with sensible
defaults. Missing files return empty lists with a warning to stderr.
"""
```

Functions to implement:

- `read_journal() -> list[dict]` -- Reads
  `$LORE_DIR/journal/data/decisions.jsonl`. Same JSONL parsing as
  `read_failures()`.
- `read_inbox() -> list[dict]` -- Reads
  `$LORE_DIR/inbox/data/observations.jsonl`. Same pattern.
- `read_neo_logs(log_name: str) -> list[dict]` -- Reads
  `$NEO_DIR/logs/{log_name}.log`. Parses the `timestamp action: details`
  format into `{"timestamp": "...", "action": "...", "details": "..."}`.
- `read_mirror_yaml(filename: str) -> list[dict]` -- Reads
  `$MIRROR_DIR/{filename}`. Requires PyYAML or shells out to `yq`. Start with
  PyYAML -- it is the one allowed external dependency.

Path resolution pattern (match `config.py:10`):

```python
import os
from pathlib import Path

LORE_DIR = Path(os.environ.get("LORE_DIR", Path.home() / "dev/lore"))
NEO_DIR = Path(os.environ.get("NEO_DIR", Path.home() / "dev/neo"))
MIRROR_DIR = Path(os.environ.get("MIRROR_DIR", Path.home() / ".mirror"))
```

Graceful degradation: if a file is missing, print a warning to stderr and
return an empty list. Never raise on missing data.

### 2. Add `correlate` to `src/praxis/analysis.py`

New function that joins failures with journal entries by timestamp proximity.

```python
def correlate(window_hours: int = 24) -> list[dict]:
    """Failures alongside journal entries within a time window.

    For each failure, find journal decisions made within window_hours
    before or after the failure timestamp. Returns list of dicts with
    'failure' and 'nearby_decisions' keys.
    """
```

Implementation:

1. Call `read_failures()` and `read_journal()` from sources
2. Parse ISO timestamps from both
3. For each failure, filter journal entries where
   `abs(failure_time - decision_time) <= window_hours`
4. Return paired results sorted by failure timestamp

### 3. Add `stale` to `src/praxis/analysis.py`

```python
def stale(days: int = 7) -> dict:
    """Observations and judgments aging without action.

    Returns dict with 'stale_observations' (inbox entries older than
    threshold with status='raw') and 'stale_count'.
    """
```

Implementation:

1. Call `read_inbox()` from sources
2. Filter entries where `status == "raw"` and timestamp older than `days`
3. Return aged entries sorted oldest first

### 4. Wire commands into `bin/praxis`

Add two subcommands following the existing pattern at `bin/praxis:87-120`:

```python
# -- correlate --
p = sub.add_parser("correlate", help="Failures alongside nearby decisions")
p.add_argument("--window", type=int, default=24, help="Hours (default: 24)")
p.add_argument("--json", action="store_true")
p.set_defaults(func=cmd_correlate)

# -- stale --
p = sub.add_parser("stale", help="Observations aging without action")
p.add_argument("--days", type=int, default=7, help="Age threshold (default: 7)")
p.add_argument("--json", action="store_true")
p.set_defaults(func=cmd_stale)
```

Human-readable output for `correlate`:

```text
  2026-02-14 10:30  fail-001  NonZeroExit -- git push failed
    nearby: dec-abc123 "Use feature branches for risky changes" (2h before)
    nearby: dec-def456 "Switch to SSH auth" (4h after)
```

Human-readable output for `stale`:

```text
  Stale observations (> 7 days):
    obs-0d37e7e3  2026-02-14  "Test observation from Praxis facade"  (1 day old)
  Total: 1 stale, 2 promoted
```

### 5. Move path constants to `config.py`

Add `LORE_DIR`, `NEO_DIR`, `MIRROR_DIR` to `config.py` alongside the existing
`LORE_DIR` (already there at line 10). Add:

```python
NEO_DIR = Path(os.environ.get("NEO_DIR", Path.home() / "dev/neo"))
MIRROR_DIR = Path(os.environ.get("MIRROR_DIR", Path.home() / "dev/mirror"))
```

Then import these in `sources.py` from `praxis.config` instead of resolving
paths locally.

### 6. Update CLAUDE.md

Add to the Commands table:

```text
| `praxis correlate [--window N]`             | Failures alongside nearby decisions |
| `praxis stale [--days N]`                   | Observations aging without action   |
```

Add to Architecture section:

```text
- **Data sources**: Reads from Lore (journal, inbox, failures), Neo (logs), Mirror (captures)
```

## What NOT to Do

- Do not add `friction`, `drift`, `blind-spots`, or `health` commands. Those
  are Phase 2. This plan covers Phase 1 only.
- Do not write to any project. Praxis is read-only. All output goes to stdout.
- Do not modify `failure.py` or the existing analysis functions (`summarize`,
  `triggers`, `timeline`). New code extends, not replaces.
- Do not add dependencies beyond PyYAML. Stdlib + PyYAML is the ceiling.
- Do not parse Neo logs with regex. Use simple `split(" ", 2)` on the timestamp
  and remainder. Neo log format is stable.
- Do not read Council initiative files yet. Markdown checkbox parsing is Phase 2
  scope.
- Do not replace or duplicate Lore's shell-native failure commands (`lore fail`,
  `lore failures`, `lore triggers`). Praxis reads the same JSONL file for
  programmatic analysis; Lore owns the CLI interface for shell consumers.

## Files to Create/Modify

| File                     | Change                                        |
| ------------------------ | --------------------------------------------- |
| `src/praxis/sources.py`  | New: data access layer (4 reader functions)   |
| `src/praxis/config.py`   | Add NEO_DIR, MIRROR_DIR path constants        |
| `src/praxis/analysis.py` | Add `correlate()` and `stale()` functions     |
| `bin/praxis`             | Add `correlate` and `stale` subcommands       |
| `CLAUDE.md`              | Add new commands and data sources description |

## Acceptance Criteria

- [x] `sources.py` reads Lore journal JSONL and returns list of dicts
- [x] `sources.py` reads Lore inbox JSONL and returns list of dicts
- [x] `sources.py` reads Neo logs and returns list of dicts
- [x] Missing files produce stderr warning and empty list, not crash
- [x] `praxis correlate` shows failures alongside journal entries within window
- [x] `praxis correlate --window 1` narrows to 1-hour window
- [x] `praxis stale` shows raw observations older than threshold
- [x] `praxis stale --days 0` shows all raw observations regardless of age
- [x] Both commands support `--json` flag
- [x] Existing commands (`log`, `failures`, `triggers`, `timeline`) unchanged
- [x] No writes to any project directory

## Testing

```bash
# Verify sources read real data
python3 -c "
import sys; sys.path.insert(0, 'src')
from praxis.sources import read_journal, read_inbox
j = read_journal(); print(f'Journal: {len(j)} entries')
i = read_inbox(); print(f'Inbox: {len(i)} entries')
"

# Correlate (may show no matches if no failures logged yet)
bin/praxis correlate --json

# Stale with zero threshold (shows all raw observations)
bin/praxis stale --days 0

# Verify graceful degradation
LORE_DIR=/nonexistent bin/praxis stale --days 0 2>&1 | grep -i warn

# Verify existing commands still work
bin/praxis failures --json
bin/praxis triggers
```
