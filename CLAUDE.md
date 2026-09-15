# Praxis — Pragmatic Leverage

Operational synthesis layer over Lore. Reads from Lore's memory, synthesizes actionable views.

## Ecosystem

> **You are here: Praxis** -- Synthesis layer over Lore

| Project     | Role                        |
| ----------- | --------------------------- |
| **Lore**    | Memory, registry, intent    |
| **Council** | Cross-project decisions     |
| **Praxis**  | Synthesis layer over Lore   |
| **Geordi**  | Unified API + GUIs          |
| **Forge**   | Spec, prototype, synthesize |

Praxis reads from Lore. Full map: ~/dev/council/mainstay/ecosystem.md

## Onboarding

New to the stack? Start with
[Getting Started](~/dev/council/docs/getting-started.md) -- a 30-minute path
from zero to productive.

## Commands

| Command               | Action                                          |
| --------------------- | ----------------------------------------------- |
| `praxis status`       | Active goals, current blockers, ecosystem pulse |
| `praxis next`         | Prioritized work queue                          |
| `praxis blockers`     | Failures, stale items, friction points          |
| `praxis health`       | Single-page ecosystem summary                   |
| `praxis impact`       | Blast radius across ecosystem                   |
| `praxis friction`     | Failures at project boundaries                  |
| `praxis blind-spots`  | Recurring failures without decisions            |
| `praxis refinement`   | Decisions ripe for promotion to patterns        |
| `praxis context`      | Filtered context brief for agent prompts        |
| `praxis verify`       | Ground-truth verification against code          |
| `praxis drift`        | Decision reversals over time                    |
| `praxis stale`        | Signals aging without action                    |
| `praxis overlap`      | Command name conflicts across projects          |
| `praxis complexity`   | Projects exceeding complexity thresholds        |
| `praxis correlate`    | Failures alongside nearby decisions             |
| `praxis undocumented` | Decisions and patterns lacking rationale        |
| `praxis fleet`        | Fleet status: agents, tasks, merge queue        |
| `praxis emit`         | Fleet dispatch payload to Blueprint inbox       |

## Architecture

- **Storage**: None. Lore owns all data.
- **Reads from**: Lore (intent, failures, inbox, journal, patterns), SpecTrace (requirements, test results)
- **Writes**: None. Record decisions and failures with the `lore` CLI directly.
- **Data path**: `$LORE_DATA_DIR`, falling back to `$LORE_DIR`, then `~/dev/lore`
- **Dependencies**: Python 3.10+, PyYAML, Lore. `DATABASE_URL` routes
  SpecTrace reads through Postgres and needs the `spectrace` extra
  (`pip install -e .[spectrace]`, adds psycopg)

## Layout

```text
bin/praxis              CLI entry point
src/praxis/
  lore.py               Read from Lore's data files
  synthesis.py          Combine sources into actionable views
```

## Development

```bash
make check   # lint + format + test (matches CI)
make test    # pytest only
make lint    # ruff check
make format  # ruff format src/ tests/
```

## Completed Plans

- `plans/add-ci.md` -- CI workflow, ruff config, Makefile (commit `c05a3a9`)
