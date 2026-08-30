---
tags: [praxis, ecosystem, synthesis]
priority: high
status: active
risk_level: medium
verification_method: test
---

# Praxis — operational synthesis

What Praxis promises to the operator who runs `praxis status`. Praxis reads
Lore's memory, spec-trace's verification database, and the fleet database, then
synthesizes views that answer "where am I, and what is blocked". It owns no
storage except the fleet payloads it emits.

Requirements below describe behavior verified by the suite in
`tests/`, not intended behavior.

## REQ-PRX-000: Synthesis surface

Praxis answers operational questions by reading state other projects own. Every
read degrades to an empty result when the underlying store is absent, so a
missing Lore directory or fleet database yields a partial answer rather than a
crash.

Each reader and each synthesized view below is a child of this requirement.

## REQ-PRX-001: Read Lore memory files

Praxis reads Lore's stores from `$LORE_DATA_DIR`, falling back to `$LORE_DIR`,
falling back to `~/dev/lore`: failures, evidence, signals, decisions, goals,
registry, and patterns.

Missing files return empty results. Malformed JSONL raises rather than being
skipped silently. Append-only stores collapse to the last written record per
`id`, so a superseded signal never appears twice. Reads pass through a
thread-safe TTL cache that `cache_clear()` invalidates.

## REQ-PRX-002: Synthesize operational views

Praxis derives `status`, `next`, `blockers`, `health`, `context`, `verify`,
`stale`, `friction`, `blind-spots`, `refinement`, `drift`, `correlate`,
`overlap`, `complexity`, and `undocumented` from the readers.

Each view returns a status token chosen by explicit thresholds rather than a
free-form judgment: `status` reports a pulse of `attention`, `active`, or
`clear`; `verify` reports `unavailable`, `drifted`, `uncovered`, `verified`, or
`partial`; `health` reports `healthy`, `attention`, or `critical`.

`context` ranks candidates by a weighted relevance score and fills sections
until a token budget is spent, marking the result `truncated` when it stops
early. Ground truth is appended outside the budget so it is never dropped.

## REQ-PRX-003: Expose the command line

`praxis <command>` exposes one subcommand per synthesized view. Every command
except `emit` accepts `--json` and prints the view as indented JSON.

A missing store, an invalid value, or a runtime failure prints `Error: <message>`
to stderr and exits non-zero. Invoking `praxis` with no command exits non-zero
rather than printing an empty report.

## REQ-PRX-004: Read spec-trace verification state

Praxis reads spec-trace's SQLite database directly to report coverage, orphan
requirements, stale links, high-risk issues, the latest test run, and
integration risks.

`db_available()` is false when the file is missing or the requirements table is
absent, and every dependent view degrades to `unavailable` rather than raising.
An orphan is a leaf requirement that is not a draft and carries no test link,
reported worst risk first.

## REQ-PRX-005: Read fleet state

Praxis reads the fleet database for agents, tasks, events, failures, token
usage, invariant violations, expired leases, the merge queue, rule-of-three
violations, blind spots, and scope overlap.

A missing database or a query error returns an empty list, so fleet views
degrade to `unavailable` instead of failing the whole report.

## REQ-PRX-006: Compute cross-project impact

`praxis impact --base <ref> --head <ref>` builds an impact graph across the
configured project roots from each project's `spectrace-map.yaml`,
`contract.snapshot.json`, and git history.

Git refs are validated before they reach a subprocess; an invalid ref raises
rather than being passed through. Co-change edges require three occurrences in a
rolling 30-day window and decay after 90 days. The traversal is bidirectional,
bounded by depth, and classifies reached nodes as requirements or modules before
scoring risk as low, medium, high, or critical.

## REQ-PRX-007: Emit fleet payloads

`praxis emit --team <name> --task <spec>` writes a timestamped YAML payload
naming the team, runtime, and tasks into the blueprint inbox.

The output directory comes from `$BLUEPRINT_INBOX` and is created when absent.
Mismatched task and agent-type counts are rejected before anything is written.
This is the only path by which Praxis writes.
