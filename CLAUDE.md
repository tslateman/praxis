# Praxis -- Failure Journals

Structured failure journals and analysis. The "Compounding Wisdom" engine.

## Commands

| Command                                                 | Action                              |
| ------------------------------------------------------- | ----------------------------------- |
| `praxis log <mission> <step> <tool> <error_type> <msg>` | Write failure journal entry         |
| `praxis failures [--type TYPE] [--mission ID]`          | Query failures                      |
| `praxis triggers [--threshold N]`                       | Error types hitting Rule of Three   |
| `praxis timeline <mission>`                             | Mission failure history             |
| `praxis correlate [--window N]`                         | Failures alongside nearby decisions |
| `praxis stale [--days N]`                               | Observations aging without action   |

## Error Type Vocabulary

`UserDeny`, `HardDeny`, `NonZeroExit`, `Timeout`, `ToolError`, `LogicError`

## Architecture

- **Storage**: JSONL at `~/dev/lore/failures/data/failures.jsonl`
- **Data sources**: Reads from Lore (journal, inbox, failures), Neo (logs), Mirror (captures)
- **Dependencies**: Python 3.10+ (stdlib only)
- **Write convention**: Praxis owns write logic; Lore owns storage

## Layout

```text
bin/praxis              CLI entry point
src/praxis/
  config.py             Path resolution (LORE_DIR)
  failure.py            Write failure journals (JSONL)
  analysis.py           Query, triggers, timeline
```

## Pending Plans

Check `plans/` for session pickup files before starting new work.

## Provenance

Adapted from `~/dev/praxis-rdx/failure.py`. The executor, proxy, and planner
were dropped -- Claude Code is the runtime. The failure journals and analysis
layer are the genuinely novel contribution.
