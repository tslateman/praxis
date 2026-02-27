Status: Completed

# Plan: Watchdog Failure Ingest

## Context

Praxis depends on explicit `lore fail` calls. We want a Tier 0 watchdog that
detects repeated command failures and records them automatically. This makes
Rule of Three triggers mechanical instead of agent-dependent.

## What to Do

### 1. Add a `watchdog` command

Create `praxis watchdog` to run a lightweight loop that watches a command and
records repeated failures to Lore. A simple starting shape:

- `praxis watchdog --cmd "make test" --project praxis --window 10m --threshold 3`
- Executes the command on a configurable interval (default 5m)
- Hashes stderr/stdout and exit code to identify repeated failures
- When the same signature repeats `threshold` times within `window`, call:
  `lore fail ToolError "<summary>" --project <project> --details "<sig>"`

### 2. Persist minimal state

Store the last N failure signatures in a local state file so the watchdog can
survive restarts. Use a JSON file in `~/.local/share/praxis/`.

### 3. Add `praxis watchdog report`

Provide a quick summary of recent failures and their counts so users can see
what the watchdog has captured without opening Lore.

## What NOT to Do

- Do not run commands concurrently. One command at a time.
- Do not attempt to parse stack traces beyond a short summary.
- Do not write to Lore when the command succeeds.
- Do not store raw secrets in the state file. Redact long tokens.

## Files to Modify

- `src/praxis/cli.py` -- add `watchdog` subcommand
- `src/praxis/watchdog.py` -- new watchdog logic
- `src/praxis/lore.py` -- helper to call `lore fail` with details
- `pyproject.toml` -- add entry point if needed
- `README.md` -- document new command

## Acceptance Criteria

- [x] Repeated failures within the window create a single `lore fail` entry
- [x] Distinct failure signatures remain separate
- [x] State file persists between runs
- [x] `praxis watchdog report` lists recent signatures and counts

## Testing

```bash
praxis watchdog --cmd "false" --project praxis --interval 1s --threshold 2
praxis watchdog report
```
