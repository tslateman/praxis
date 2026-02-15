# Praxis -- Failure Journals

Structured failure journals and analysis. The "Compounding Wisdom" engine.

## Commands

| Command                                                 | Action                            |
| ------------------------------------------------------- | --------------------------------- |
| `praxis log <mission> <step> <tool> <error_type> <msg>` | Write failure journal entry       |
| `praxis failures [--type TYPE] [--mission ID]`          | Query failures                    |
| `praxis triggers [--threshold N]`                       | Error types hitting Rule of Three |
| `praxis timeline <mission>`                             | Mission failure history           |

## Error Type Vocabulary

`UserDeny`, `HardDeny`, `NonZeroExit`, `Timeout`, `ToolError`, `LogicError`

## Architecture

- **Storage**: JSONL at `~/dev/lineage/failures/data/failures.jsonl`
- **Dependencies**: Python 3.10+ (stdlib only)
- **Write convention**: Praxis owns write logic; Lineage owns storage

## Layout

```text
bin/praxis              CLI entry point
src/praxis/
  config.py             Path resolution (LINEAGE_DIR)
  failure.py            Write failure journals (JSONL)
  analysis.py           Query, triggers, timeline
```

## Provenance

Adapted from `~/dev/praxis-rdx/failure.py`. The executor, proxy, and planner
were dropped -- Claude Code is the runtime. The failure journals and analysis
layer are the genuinely novel contribution.
