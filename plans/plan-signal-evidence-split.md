# Signal/Evidence Primitive Split

Replace Lore's "observation" primitive with two distinct primitives — **signal**
(transient inbox) and **evidence** (durable facts with provenance).

## Problem

Lore's "observation" conflates transient signals with durable evidence. Observations
that survive triage must become decisions or get lost — no way to persist a fact
that isn't a choice. Praxis can't score or surface what Lore can't name.

## Goal

Give Lore a way to retain durable facts that aren't decisions, so Praxis can
surface them as knowledge instead of losing them at triage.

## Success Criteria

- `lore observe` writes a raw signal to `inbox/data/signals.jsonl`
- `lore capture` evaluates context and promotes signals to evidence, decision,
  or discard
- Evidence stored in `evidence/data/evidence.jsonl` (append-only,
  last-version-wins)
- `praxis context` includes evidence upstream of patterns: **evidence → patterns
  → anti-patterns → decisions → goals**
- Evidence feeds back into decisions (cited_by linkage)
- Existing `observations.jsonl` entries migrated and reclassified
- Decisions unchanged

## Scope

### In scope

- New `evidence/` data store in Lore (JSONL, append-only)
- Rename observation internals to signal (`inbox/data/signals.jsonl`)
- `lore capture` promotion logic (AI classifies: signal / evidence / decision)
- Praxis `lore.py` readers for evidence
- Praxis `synthesis.py` context scoring for evidence (upstream of patterns)
- Evidence-decision back-references (`cited_by` / `cites`)
- Migration script for existing `observations.jsonl`

### Out of scope

- Changes to decision primitive or lifecycle
- Changes to pattern/anti-pattern primitives
- Memory MCP server integration (follow-up)
- Geordi API endpoints for evidence (follow-up)

## Data Model

### Evidence

```jsonl
{
  "id": "evi-a3f21b",
  "timestamp": "...",
  "source": "dark-factory-research",
  "content": "AI liability insurance is evaporating...",
  "confidence": "preliminary",
  "tags": [
    "dark-factory",
    "insurance"
  ],
  "cited_by": [],
  "provenance": "web-research"
}
```

Confidence lifecycle: `preliminary → confirmed → contested → superseded`

### Signal (renamed observation)

Same shape as today's observation, renamed. Status lifecycle unchanged:
`raw → promoted | discarded`

## Build Sequence

1. **Lore**: evidence store + CLI (`lore evidence list`, evidence JSONL reader)
2. **Lore**: rename observation → signal in inbox internals, update `lore observe`
3. **Lore**: update `lore capture` to support three-way promotion
   (signal / evidence / decision)
4. **Praxis**: add evidence readers to `lore.py`
5. **Praxis**: integrate evidence into `synthesis.py` context scoring
   (upstream of patterns)
6. **Migration**: reclassify existing `observations.jsonl` entries
   (separate follow-up)

## Context Priority Order

```
evidence → patterns → anti-patterns → decisions → goals
```

## Open Questions

- Should `cited_by` auto-populate when a decision references evidence, or is
  that manual linkage via `lore capture`?
- Does the confidence lifecycle need CLI commands (`lore evidence confirm <id>`),
  or does `lore capture` handle transitions too?
- Should `praxis context` score evidence differently than decisions (heavier
  weight on recency, lighter on outcome since evidence has no outcome)?
