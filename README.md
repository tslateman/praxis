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
            health, triggers
```

Praxis reads from Lore's memory (intent, failures, inbox, journal, patterns) and synthesizes actionable views. It owns no storage — Lore owns all writes.

## Setup

### Requirements

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- Lore at `~/dev/lore/`

No installation step. No `pip install`. The CLI runs directly from the repo.

### Add to PATH

```bash
export PATH="$HOME/dev/praxis/bin:$PATH"
```

## Commands

### Operational

| Command           | Description                            |
| ----------------- | -------------------------------------- |
| `praxis status`   | Where am I? Active goals, blockers     |
| `praxis next`     | What should I work on now?             |
| `praxis blockers` | Failures, stale observations, friction |
| `praxis health`   | Ecosystem pulse — single-page summary  |

### Analysis

| Command              | Description                           |
| -------------------- | ------------------------------------- |
| `praxis triggers`    | Error types hitting Rule of Three     |
| `praxis friction`    | Failures mapped to project boundaries |
| `praxis blind-spots` | Recurring failures without decisions  |
| `praxis stale`       | Observations aging without action     |
| `praxis correlate`   | Failures alongside nearby decisions   |

### Delegation (writes go to Lore)

| Praxis Shortcut         | Delegates To           |
| ----------------------- | ---------------------- |
| `praxis fail <args>`    | `lore fail <args>`     |
| `praxis observe <text>` | `lore observe <text>`  |
| `praxis decide <text>`  | `lore remember <text>` |

## Design

Praxis is a pure facade. It:

1. **Reads** from Lore's JSONL files (failures, inbox, journal, intent)
2. **Synthesizes** actionable views (status, next, blockers)
3. **Delegates** writes to Lore CLI

No direct file writes. No duplicate storage. Lore is the single source of truth.

## Development History

See `plans/` for completed implementation plans.
