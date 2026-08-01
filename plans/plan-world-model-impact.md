Status: Ready

# Plan: World Model Phase 1 -- Ecosystem Impact

## Context

Council opened the World Model initiative
(`council/initiatives/world-model.md`): a current-state and dynamics projection
over Lore, owned by Praxis. Phase 1 delivers ecosystem-level impact analysis:
"contract X changed, which consumers break?" -- the GitNexus upstream-impact
move at ecosystem grain.

The pieces mostly exist. Lore's registry holds typed relationship edges
(`~/.local/share/lore/registry/data/relationships.yaml`) recording which paths
each consumer reads. `contracts.yaml` in the same directory is empty -- a seam
waiting to be filled. Praxis already ships `praxis impact`
(`src/praxis/impact.py`, built over spectrace-map + git co-change). This plan
wires them together; it builds nothing beside them.

## What to Do

### 1. Seed contracts.yaml

Generate an initial `contracts.yaml` covering the six active projects (Lore,
Council, Praxis, Geordi, Shipyard, Forge). Derive candidate contracts from
Council's drift-detector output and `relationships.yaml` read/write paths. Each
contract entry: `name`, `owner` (project), `surface` (paths or interfaces),
`consumers` (project + paths read), `last_verified` (ISO date). Output is a
draft for human curation, not an auto-committed artifact.

### 2. Extend praxis impact with registry walking

Add a `--contract <name>` mode to `praxis impact` in `src/praxis/impact.py`:

- Load `contracts.yaml` + `relationships.yaml` via the existing Lore file I/O
  helpers (`src/praxis/lore.py`).
- Given a contract (optionally narrowed by `--path`), flag every consumer
  whose read paths intersect the contract surface.
- Walk onward transitively: consumers that are themselves contract owners
  propagate to their consumers. Plain BFS; cap depth at 3 like GitNexus
  (d=1 WILL BREAK, d=2 LIKELY AFFECTED, d=3 MAY NEED TESTING).
- Render as the existing impact report format, one section per depth.

### 3. Synthetic contract-change test

Add a test fixture with a toy registry (3 projects, 2 contracts, known
consumer graph). Assert: a change to contract A flags exactly its consumers at
the right depths, and never flags a non-consumer.

## What NOT to Do

- Do not create a new store. Read Lore's registry files in place; write
  nothing except the seeded `contracts.yaml` draft.
- Do not build causal inference. Transitive closure over typed edges only.
- Do not touch the memory MCP in this phase.
- Do not auto-commit the seeded `contracts.yaml`; the human curates it.
- Do not break the existing `praxis impact` spectrace/co-change modes.

## Files to Create/Modify

- `src/praxis/impact.py` -- add contract-walk mode
- `src/praxis/lore.py` -- registry file readers if not already present
- `src/praxis/cli.py` -- `--contract` / `--path` flags on `impact`
- `tests/test_impact_contracts.py` -- synthetic graph test
- `~/.local/share/lore/registry/data/contracts.yaml` -- seeded draft (human
  curates before commit)
- `README.md` -- document the new mode

## Acceptance Criteria

- [ ] `contracts.yaml` drafted for all six active projects and curated by the
      human
- [ ] `praxis impact --contract <name>` lists affected consumers with the
      paths they read, grouped by depth
- [ ] Transitive walk capped at depth 3 with GitNexus-style risk labels
- [ ] Synthetic test: all consumers flagged, zero false positives
- [ ] Existing `praxis impact` modes unchanged (test suite passes)

## Testing

```bash
cd ~/dev/praxis
uv run pytest tests/test_impact_contracts.py -v
uv run pytest  # full suite, no regressions
praxis impact --contract lore-registry --path registry/data/relationships.yaml
```
