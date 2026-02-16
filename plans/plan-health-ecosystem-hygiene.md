# Plan: Extend Health to Ecosystem Hygiene

## Status

**Status:** Complete — implemented 2026-02-16

## Context

`praxis health` synthesizes failure signals: failure counts, triggers, stale observations, blind spots, friction. But failures are one of five sources Praxis reads (intent, failures, inbox, journal, patterns).

Lore is addressing IA issues: duplicate commands, cognitive load, undocumented decisions. Praxis can surface these operationally — not as new commands, but as additional signals in `health`.

## Design Principle

Consolidate, don't sprawl. One command with richer synthesis beats three commands that fragment the interface.

## New Signals

| Signal       | Source                   | Question               | Threshold                   |
| ------------ | ------------------------ | ---------------------- | --------------------------- |
| Overlap      | CLI help across projects | What confuses users?   | Commands with same name     |
| Complexity   | Command/option counts    | What overwhelms users? | >10 commands, >5 options    |
| Undocumented | journal + patterns       | What lacks rationale?  | Decisions without rationale |

## What Was Done

### 1. Added `patterns()` and `projects()` to `lore.py`

- `patterns()` reads from `patterns/data/patterns.yaml`
- `projects()` extracts project names from registry dependencies

### 2. Added `ecosystem_overlap()` to `synthesis.py`

- Parses CLAUDE.md files for command names
- Handles two formats: code blocks (`project command`) and table rows
- Flags commands with identical names in different projects

### 3. Added `ecosystem_complexity()` to `synthesis.py`

- Counts commands per project from CLAUDE.md
- Flags projects exceeding 10-command threshold

### 4. Added `undocumented()` to `synthesis.py`

- Finds decisions without `rationale` field
- Finds patterns without `problem` or `context` fields

### 5. Extended `health()` with new signals

- Added `overlap_count`, `complexity_warnings`, `undocumented_decisions`, `undocumented_patterns` to summary
- Updated status logic to include hygiene issues in "attention" threshold

### 6. Extended `cmd_health()` CLI output

- Displays Overlap, Complexity, and Undocumented sections when present

## Files Modified

| File                      | Change                                   |
| ------------------------- | ---------------------------------------- |
| `src/praxis/lore.py`      | Added `patterns()`, `projects()`         |
| `src/praxis/synthesis.py` | Added ecosystem hygiene functions        |
| `src/praxis/synthesis.py` | Extended `health()` with hygiene signals |
| `bin/praxis`              | Extended `cmd_health()` output           |

## Verification

```bash
# Health shows new signals
bin/praxis health

# JSON includes all fields
bin/praxis health --json

# Individual functions work
python3 -c "
import sys; sys.path.insert(0, 'src')
from praxis import synthesis
print(synthesis.ecosystem_overlap())
print(synthesis.ecosystem_complexity())
print(synthesis.undocumented())
"
```

## Decisions Made

1. **Command discovery**: Parse CLAUDE.md rather than runtime `--help`. Faster, works offline, but may be stale if CLAUDE.md diverges from actual commands.

2. **Thresholds**: 10 commands for complexity warning. Configurable via function parameter.

3. **Overlap detection**: Exact name match only. Similar names (edit distance) deferred — exact matches are the clearer signal.
