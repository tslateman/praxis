# Plan: Phase 2 -- Neo/Mirror Integration + Friction + Blind Spots

## Status

**Status:** Complete -- implemented 2026-02-15

## Context

Phase 1 (complete) added:
- `sources.py` — readers for journal, inbox, Neo logs, Mirror YAML
- `correlate` command — failures alongside nearby decisions
- `stale` command — observations aging without action

Phase 2 adds:
- Registry reader for cross-project dependency analysis
- `friction` command — map failures to project boundaries
- `blind-spots` command — recurring failures with no journal entry

## What Was Done

### 1. Added registry reader to `src/praxis/sources.py`

- Added `REGISTRY_FILE` constant to `config.py`
- Added `read_registry()` function that reads YAML and returns dict

### 2. Added `friction` to `src/praxis/analysis.py`

- Joins failures to registry relationships by extracting project names from mission identifiers
- Returns list of dicts with 'boundary', 'failure_count', 'error_types', 'missions'

### 3. Added `blind_spots` to `src/praxis/analysis.py`

- Groups failures by error_type + mission
- Finds patterns with >= threshold occurrences and no nearby journal entry (±24h)
- Returns dict with 'orphaned_failures', 'blind_spot_count', 'suggestions'

### 4. Wired commands into `bin/praxis`

- Added `cmd_friction()` and `cmd_blind_spots()` functions
- Added subparsers for `friction` and `blind-spots` commands
- Both support `--json` flag

## Files Modified

| File                     | Change                                      |
| ------------------------ | --------------------------------------------- |
| `src/praxis/config.py`   | Added `REGISTRY_FILE` constant               |
| `src/praxis/sources.py`  | Added `read_registry()` function              |
| `src/praxis/analysis.py` | Added `friction()` and `blind_spots()` functions |
| `bin/praxis`             | Added `friction` and `blind-spots` subcommands |

## Verification

```bash
# Registry reader works
python3 -c "
import sys; sys.path.insert(0, 'src')
from praxis.sources import read_registry
r = read_registry()
print(f'Dependencies: {len(r.get(\"dependencies\", {}))}')
"

# Commands work
bin/praxis friction
bin/praxis blind-spots
bin/praxis friction --json

# Graceful degradation
LORE_DIR=/nonexistent bin/praxis friction 2>&1 | grep -i warn

# Existing commands unchanged
bin/praxis failures
bin/praxis triggers
```

## Phase 3

Next: `praxis health` — single-page ecosystem summary for session start.
