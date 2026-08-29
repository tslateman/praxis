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

<!-- gitnexus:start -->

# GitNexus — Code Intelligence

This project is indexed by GitNexus as **praxis** (690 symbols, 1115 relationships, 26 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource                                | Use for                                  |
| --------------------------------------- | ---------------------------------------- |
| `gitnexus://repo/praxis/context`        | Codebase overview, check index freshness |
| `gitnexus://repo/praxis/clusters`       | All functional areas                     |
| `gitnexus://repo/praxis/processes`      | All execution flows                      |
| `gitnexus://repo/praxis/process/{name}` | Step-by-step execution trace             |

## CLI

| Task                                         | Read this skill file                                        |
| -------------------------------------------- | ----------------------------------------------------------- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md`       |
| Blast radius / "What breaks if I change X?"  | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?"             | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md`       |
| Rename / extract / split / refactor          | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md`     |
| Tools, resources, schema reference           | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md`           |
| Index, status, clean, wiki CLI commands      | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md`             |

<!-- gitnexus:end -->
