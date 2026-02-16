# Praxis — Pragmatic Leverage

Operational synthesis layer over Lore. Reads from Lore's memory, synthesizes actionable views.

## Commands

| Command              | Action                                          |
| -------------------- | ----------------------------------------------- |
| `praxis status`      | Active goals, current blockers, ecosystem pulse |
| `praxis next`        | Prioritized work queue                          |
| `praxis blockers`    | Failures, stale items, friction points          |
| `praxis health`      | Single-page ecosystem summary                   |
| `praxis triggers`    | Error types hitting Rule of Three               |
| `praxis friction`    | Failures at project boundaries                  |
| `praxis blind-spots` | Recurring failures without decisions            |
| `praxis stale`       | Observations aging without action               |

## Architecture

- **Storage**: None. Lore owns all data.
- **Reads from**: Lore (intent, failures, inbox, journal, patterns)
- **Writes via**: Delegation to `lore` CLI
- **Dependencies**: Python 3.10+, PyYAML, Lore

## Layout

```text
bin/praxis              CLI entry point
src/praxis/
  lore.py               Read from Lore's data files
  synthesis.py          Combine sources into actionable views
```

## Pending Plans

Check `plans/` for session pickup files before starting new work.
