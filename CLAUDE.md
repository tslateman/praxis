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
| `praxis triggers`     | Error types hitting Rule of Three               |
| `praxis friction`     | Failures at project boundaries                  |
| `praxis blind-spots`  | Recurring failures without decisions            |
| `praxis refinement`   | Decisions ripe for promotion to patterns        |
| `praxis context`      | Filtered context brief for agent prompts        |
| `praxis stale`        | Observations aging without action               |
| `praxis overlap`      | Command name conflicts across projects          |
| `praxis complexity`   | Projects exceeding complexity thresholds        |
| `praxis correlate`    | Failures alongside nearby decisions             |
| `praxis undocumented` | Decisions and patterns lacking rationale        |

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

## Development

```bash
make check   # lint + format + test (matches CI)
make test    # pytest only
make lint    # ruff check
make format  # ruff format --check
```

## Completed Plans

- `plans/add-ci.md` -- CI workflow, ruff config, Makefile (commit `c05a3a9`)
