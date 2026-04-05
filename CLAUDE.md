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
| `praxis stale`        | Observations aging without action               |
| `praxis overlap`      | Command name conflicts across projects          |
| `praxis complexity`   | Projects exceeding complexity thresholds        |
| `praxis correlate`    | Failures alongside nearby decisions             |
| `praxis undocumented` | Decisions and patterns lacking rationale        |

## Architecture

- **Storage**: None. Lore owns all data.
- **Reads from**: Lore (intent, failures, inbox, journal, patterns), SpecTrace (requirements, test results)
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

<!-- gitnexus:start -->

# GitNexus — Code Intelligence

This project is indexed by GitNexus as **praxis** (543 symbols, 1606 relationships, 47 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/praxis/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool             | When to use                   | Command                                                                 |
| ---------------- | ----------------------------- | ----------------------------------------------------------------------- |
| `query`          | Find code by concept          | `gitnexus_query({query: "auth validation"})`                            |
| `context`        | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})`                              |
| `impact`         | Blast radius before editing   | `gitnexus_impact({target: "X", direction: "upstream"})`                 |
| `detect_changes` | Pre-commit scope check        | `gitnexus_detect_changes({scope: "staged"})`                            |
| `rename`         | Safe multi-file rename        | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher`         | Custom graph queries          | `gitnexus_cypher({query: "MATCH ..."})`                                 |

## Impact Risk Levels

| Depth | Meaning                               | Action                |
| ----- | ------------------------------------- | --------------------- |
| d=1   | WILL BREAK — direct callers/importers | MUST update these     |
| d=2   | LIKELY AFFECTED — indirect deps       | Should test           |
| d=3   | MAY NEED TESTING — transitive         | Test if critical path |

## Resources

| Resource                                | Use for                                  |
| --------------------------------------- | ---------------------------------------- |
| `gitnexus://repo/praxis/context`        | Codebase overview, check index freshness |
| `gitnexus://repo/praxis/clusters`       | All functional areas                     |
| `gitnexus://repo/praxis/processes`      | All execution flows                      |
| `gitnexus://repo/praxis/process/{name}` | Step-by-step execution trace             |

## Self-Check Before Finishing

Before completing any code modification task, verify:

1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task                                         | Read this skill file                                 |
| -------------------------------------------- | ---------------------------------------------------- |
| Understand architecture / "How does X work?" | `~/.claude/skills/gitnexus-exploring/SKILL.md`       |
| Blast radius / "What breaks if I change X?"  | `~/.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?"             | `~/.claude/skills/gitnexus-debugging/SKILL.md`       |
| Rename / extract / split / refactor          | `~/.claude/skills/gitnexus-refactoring/SKILL.md`     |
| Tools, resources, schema reference           | `~/.claude/skills/gitnexus-guide/SKILL.md`           |
| Index, status, clean, wiki CLI commands      | `~/.claude/skills/gitnexus-cli/SKILL.md`             |

<!-- gitnexus:end -->
