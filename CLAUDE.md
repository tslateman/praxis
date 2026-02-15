# Praxis -- Ecosystem Facade

Smart facade providing a single entry point to the agent stack. Praxis reads
the same files as the shell tools; deleting it changes nothing.

## Commands

| Command                                   | Action                              |
| ----------------------------------------- | ----------------------------------- |
| `praxis search <query>`                   | Cross-system search                 |
| `praxis observe <text>`                   | Raw observation to Lineage inbox    |
| `praxis remember <text> -r <why>`         | Decision to Lineage journal         |
| `praxis learn <text>`                     | Pattern to Lineage patterns         |
| `praxis resume`                           | Resume session from Lineage         |
| `praxis sync`                             | Mirror to Lineage inbox (via Neo)   |
| `praxis promote <id> <decision\|pattern>` | Inbox to formal knowledge (via Neo) |
| `praxis start <mission-id>`               | Hydrate mission context (via Neo)   |
| `praxis context <project>`                | Combined Lineage + Lore context     |
| `praxis status`                           | Session and mission status          |
| `praxis registry <project>`               | Lore registry info                  |
| `praxis projects`                         | List all projects from Lore         |

## Architecture

Praxis wraps: Lineage (memory), Neo (orchestration), Lore (registry). See
`~/dev/council/mainstay/ecosystem.md` for the three-pillar model.

- **Read operations**: Python reads files directly, adds schema validation
- **Write operations**: Delegates to `lineage.sh` and Neo shell scripts
- **YAML reading**: Shells out to `yq -o=json` (no PyYAML dependency)

## Key Constraint

Praxis is deletable. It adds validation and cross-system search. The shell CLIs
remain authoritative for all write operations.

## Layout

```text
bin/praxis              Single CLI entry point
src/praxis/config.py    Path resolution (LINEAGE_DIR, NEO_DIR, LORE_DIR)
src/praxis/store.py     Reads/writes Lineage files
src/praxis/schema.py    Validates data against contracts
src/praxis/engine.py    Lifecycle: sync, promote, start, context
src/praxis/registry.py  Reads Lore registry files
src/praxis/search.py    Cross-system search
```

## Dependencies

- Python 3.10+ (stdlib only)
- `yq` for YAML reading
- `lineage.sh`, Neo scripts, Lore registry (read paths)
