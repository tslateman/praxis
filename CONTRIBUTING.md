# Contributing to Praxis

Operational synthesis over Lore. Reads from Lore's memory, produces actionable
views. No storage of its own.

## Setup

```bash
# Python 3.10+, PyYAML, Lore
pip install pyyaml

# Verify
bin/praxis status
```

## Code Style

| Convention    | Rule                                            |
| ------------- | ----------------------------------------------- |
| Python        | 3.10+, stdlib preferred, PyYAML only dependency |
| Reads         | From Lore's data files via `src/praxis/lore.py` |
| Writes        | Delegate to `lore` CLI -- never write directly  |
| Configuration | TOML for config, YAML for registries            |
| Prose         | Strunk's Elements of Style -- active, concrete  |
| Emdashes      | Never. Use double hyphens (`--`) instead        |

## Commits

Use conventional prefixes with Strunk's-style body:

```text
feat: Add blind-spots command for unaddressed failures
fix: Fix stale threshold calculation for inbox items
refactor: Extract synthesis logic from CLI entry point
```

Active voice. Omit needless words. No `Co-Authored-By` signatures.

## Architecture Rules

- **No storage**: Lore owns all data. Praxis reads and synthesizes
- **Delegation**: Writes go through the `lore` CLI, never directly to files
- **Stdlib first**: Minimize dependencies. PyYAML is the sole exception
- **Synthesis**: Combine multiple Lore sources into actionable views

## File Layout

```text
bin/praxis              CLI entry point
src/praxis/
  lore.py               Read from Lore's data files
  synthesis.py           Combine sources into actionable views
```

## Testing

```bash
# Run tests
python -m pytest

# Verify commands produce output
bin/praxis status
```

The fleet tests build a fleet.db from Shipyard's schema, so they need a
Shipyard checkout at `~/dev/shipyard`. Point `SHIPYARD_SCHEMA` at
`src/schema/fleet.sql` to use a checkout elsewhere:

```bash
SHIPYARD_SCHEMA=/path/to/shipyard/src/schema/fleet.sql python -m pytest
```

CI checks out Shipyard's `main` and reads the same file, so a schema change
that breaks Praxis turns the build red instead of passing unnoticed.

## Pull Requests

1. Branch from `main` with a descriptive name
2. Keep changes focused -- one concern per PR
3. Read existing Lore readers in `src/praxis/lore.py` before adding new ones
4. Never add runtime dependencies beyond stdlib and PyYAML
5. Check `plans/` for session pickup files before starting new work

## What Not to Do

- Don't store data -- delegate all writes to the `lore` CLI
- Don't add dependencies beyond PyYAML
- Don't duplicate Lore's data; synthesize views from it
