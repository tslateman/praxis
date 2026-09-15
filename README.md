# Praxis

Pragmatic leverage for getting shit done. The operational synthesis layer over Lore.

## The Triangle

```
Lore (intent)                spec-trace (verification)
    │                              │
    │   success_criteria           │   done_when
    │   goals → missions           │   tasks → reviews
    │                              │
    └──────────────┬───────────────┘
                   │
              Praxis (synthesis)
                   │
            status, next, blockers,
            health, context
```

Praxis reads from Lore's memory (intent, failures, inbox, journal, patterns) and synthesizes actionable views. It owns no storage — Lore owns all writes.

## Setup

### Requirements

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- Lore, with its data directory at `$LORE_DATA_DIR` (defaults to `$LORE_DIR`,
  itself defaulting to `~/dev/lore/`)

No installation step for the base CLI. It runs directly from the repo.

Set `DATABASE_URL` to read SpecTrace from the shared Postgres instead of the
local SQLite file. That path needs the `spectrace` extra:

```bash
pip install -e '.[spectrace]'
```

### Add to PATH

```bash
export PATH="$HOME/dev/praxis/bin:$PATH"
```

## Commands

### Operational

| Command           | Description                           |
| ----------------- | ------------------------------------- |
| `praxis status`   | Where am I? Active goals, blockers    |
| `praxis next`     | What should I work on now?            |
| `praxis blockers` | Failures, stale signals, friction     |
| `praxis health`   | Ecosystem pulse — single-page summary |
| `praxis context`  | Filtered context brief for agents     |
| `praxis fleet`    | Agents, tasks, merge queue            |

### Analysis

| Command               | Description                              |
| --------------------- | ---------------------------------------- |
| `praxis friction`     | Failures mapped to project boundaries    |
| `praxis blind-spots`  | Recurring failures without decisions     |
| `praxis stale`        | Signals aging without action             |
| `praxis correlate`    | Failures alongside nearby decisions      |
| `praxis refinement`   | Decisions ripe for promotion to patterns |
| `praxis drift`        | Decision reversals over time             |
| `praxis undocumented` | Decisions and patterns lacking rationale |
| `praxis overlap`      | Command name conflicts across projects   |
| `praxis complexity`   | Projects exceeding complexity thresholds |
| `praxis impact`       | Blast radius across the ecosystem        |
| `praxis verify`       | Ground-truth verification against code   |
| `praxis emit`         | Fleet dispatch payload to Blueprint      |

## Design

Praxis reads and synthesizes. It:

1. **Reads** from Lore's JSONL and YAML files (failures, inbox, journal, intent, patterns)
2. **Synthesizes** actionable views (status, next, blockers)

It writes nothing. Record decisions and failures with the `lore` CLI directly.
No duplicate storage. Lore is the single source of truth.

## Development History

See `plans/` for completed implementation plans.
