# Praxis

Ecosystem facade for Lineage, Neo, and Lore. A single Python entry point that
reads the same files the shell tools read, adds validation, and provides
cross-system search.

## Setup

### Requirements

- Python 3.10+
- [yq](https://github.com/mikefarah/yq/) (`brew install yq`)
- Lineage at `~/dev/lineage/`
- Neo at `~/dev/neo/`
- Lore at `~/dev/lore/`

No installation step. No `pip install`. The CLI runs directly from the repo
using stdlib imports and `sys.path`.

### Optional: add to PATH

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="$HOME/dev/praxis/bin:$PATH"
```

Then use `praxis` instead of `bin/praxis` everywhere below.

### Override paths

If your ecosystem lives somewhere other than `~/dev/`:

```bash
export LINEAGE_DIR="/path/to/lineage"
export NEO_DIR="/path/to/neo"
export LORE_DIR="/path/to/lore"
export MIRROR_DIR="/path/to/mirror"    # defaults to ~/.mirror
```

## Usage

### Search across all systems

```bash
praxis search "JSONL"
#   [journal] (0.9) Use JSONL for decision storage

praxis search "Praxis"
#   [pattern] (0.9) Prototype Decomposition
```

### Capture observations, decisions, and patterns

```bash
# Raw observation to Lineage inbox
praxis observe "Vector search fails on large datasets"

# Decision with rationale to Lineage journal
praxis remember "Use HNSW index" -r "Better recall at scale"

# Pattern to Lineage patterns
praxis learn "Cache invalidation" --context "Distributed systems" --solution "TTL + event-driven purge"
```

### Mirror sync and promotion

```bash
# Sync ~/.mirror/*.md into Lineage inbox (via Neo)
praxis sync

# Promote an inbox observation to a decision or pattern
praxis promote obs-abc123 decision --rationale "Needs investigation"
praxis promote obs-abc123 pattern --context "When deploying to prod"
```

### Project context

```bash
# Combined Lineage + Lore context for a project
praxis context council

# Lore registry info only
praxis registry council

# List all projects known to Lore
praxis projects
```

### Session and mission management

```bash
# Resume from a previous Lineage session
praxis resume

# Hydrate mission context from Neo
praxis start <mission-id>

# Session status -- inbox, journal, and pattern counts
praxis status
```

## Design

Praxis is a **reductive facade** -- it wraps existing tools without replacing
them.

- **Reads** happen in Python, with schema validation
- **Writes** delegate to `lineage.sh` and Neo shell scripts
- **YAML** parsed via `yq -o=json` (stdlib-only, no PyYAML)

Delete `~/dev/praxis/` and everything still works. The shell CLIs remain
authoritative.

## Layout

```text
bin/praxis              Single CLI entry point
src/praxis/
  config.py             Path resolution (env vars)
  store.py              Lineage file I/O + shell delegation
  schema.py             Data validation
  engine.py             Orchestration (sync, promote, start)
  registry.py           Lore registry reader
  search.py             Cross-system search
```

## Provenance

- `000-bootstrap-praxis.json` -- original bootstrap mission
- `000-json-over-yaml-for-bootstrap.json` -- JSON-over-YAML decision record
