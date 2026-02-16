# Plan: Phase 3 -- Health Dashboard

## Status

**Status:** Complete -- implemented 2026-02-15

## Context

Phase 1 added data readers and `correlate`/`stale` commands.
Phase 2 added `friction` and `blind-spots` commands.
Phase 3 adds `praxis health` — one command an agent runs at session start to orient.

## What Was Done

### 1. Added `health()` to `src/praxis/analysis.py`

- Aggregates: failure count, recent failures (7 days), triggers, stale observations, blind spots, friction
- Returns dict with summary counts and full results from each analysis
- Status logic: critical (blind spots or triggers >= 5), attention (stale or any triggers), healthy

### 2. Wired command into `bin/praxis`

- Added `cmd_health()` with human-readable output
- Added `health` subparser with `--json` flag

## Files Modified

| File                     | Change                  |
| ------------------------ | ----------------------- |
| `src/praxis/analysis.py` | Added `health()` function |
| `bin/praxis`             | Added `health` subcommand |

## Verification

```bash
# Health with no failures (shows healthy)
bin/praxis health

# JSON output
bin/praxis health --json

# Existing commands unchanged
bin/praxis failures
bin/praxis triggers
```

## Praxis Analysis Initiative Complete

All three phases delivered:

| Phase | Commands              | Purpose                              |
| ----- | --------------------- | ------------------------------------ |
| 1     | correlate, stale      | Cross-source queries                 |
| 2     | friction, blind-spots | Pattern detection at boundaries      |
| 3     | health                | Session-start orientation dashboard  |
