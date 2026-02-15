# Praxis

Structured failure journals and analysis for the agent ecosystem. Every failure
gets a coroner's report. Over time, these reports reveal systemic issues worth
addressing.

"Don't build the riverboat. Build the map of the river."

## Setup

### Requirements

- Python 3.10+
- Lore at `~/dev/lore/`

No installation step. No `pip install`. The CLI runs directly from the repo
using stdlib imports and `sys.path`.

### Optional: add to PATH

```bash
export PATH="$HOME/dev/praxis/bin:$PATH"
```

### Override paths

```bash
export LORE_DIR="/path/to/lore"
```

## Usage

### Log a failure

```bash
praxis log fix-auth 2 shell NonZeroExit "Command failed with exit code 1"
```

### Query failures

```bash
# All failures
praxis failures

# Filter by error type
praxis failures --type NonZeroExit

# Filter by mission
praxis failures --mission fix-auth

# Raw JSON output
praxis failures --json
```

### Detect systemic patterns

```bash
# Error types that recur >= 3 times
praxis triggers

# Custom threshold
praxis triggers --threshold 5
```

### Mission timeline

```bash
praxis timeline fix-auth
```

## Error Type Vocabulary

| Type          | Meaning                                      |
| ------------- | -------------------------------------------- |
| `UserDeny`    | Human said no                                |
| `HardDeny`    | Denylist blocked it                          |
| `NonZeroExit` | Command ran but failed                       |
| `Timeout`     | Command hung                                 |
| `ToolError`   | Tool crashed or returned garbage             |
| `LogicError`  | Output was wrong (caught by eval, not crash) |

## Design

Praxis writes failure journals as JSONL to
`~/dev/lore/failures/data/failures.jsonl`. This matches Lore's existing
conventions (`journal/data/decisions.jsonl`, `inbox/data/observations.jsonl`).

Stdlib only. No PyYAML, no external dependencies.

## Library Usage

```python
from praxis.failure import log_failure
from praxis.analysis import summarize, triggers, timeline

log_failure("fix-auth", 2, "shell", "NonZeroExit", "Command failed")
result = summarize(error_type="NonZeroExit")
hot = triggers(threshold=3)
history = timeline("fix-auth")
```

## Provenance

Adapted from `~/dev/praxis-rdx/failure.py`. That prototype included an executor,
proxy, and planner -- all dropped because Claude Code serves those roles. The
failure journals and analysis layer are the genuinely novel contribution.

The architectural patterns session that produced `praxis-rdx` concluded: the
proxy and executor reinvent Claude Code. The failure journals and learning layer
are what's new. This project keeps the map and drops the riverboat.
