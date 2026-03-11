Status: Draft

# Plan: Overstory Integration for SpecTrace + Lore

## Context

Overstory provides multi-agent orchestration (worktrees, merge queue, runtime
adapters). SpecTrace is the system of record for tasks. Lore captures decisions
and failures. Praxis synthesizes status and next actions. We need a minimal
integration spec so Overstory can execute SpecTrace tasks while keeping task
state and memory in sync.

## Goals

- Use SpecTrace tasks as the canonical work queue for Overstory agents.
- Sync SpecTrace task state with Overstory lifecycle events.
- Emit Lore decisions and failures automatically on merge and failure.
- Keep Praxis as the synthesis layer, not the orchestrator.

## Non-Goals

- Replace SpecTrace's task model or review workflow.
- Rebuild orchestration in Praxis.
- Enforce a single review flow across all teams.

## Lifecycle Mapping

| SpecTrace Status               | Overstory Event      | Trigger         |
| ------------------------------ | -------------------- | --------------- |
| UNCLAIMED → CLAIMED            | `ov sling <task-id>` | Agent spawn     |
| CLAIMED → IN_PROGRESS          | `ov agent start`     | Work begins     |
| IN_PROGRESS → READY_FOR_REVIEW | `ov agent submit`    | Work done       |
| READY_FOR_REVIEW → APPROVED    | Reviewer approves    | Review step     |
| APPROVED → MERGED              | `ov merge`           | Merge completed |

## Required Hooks (MVP)

### On Agent Spawn

```
python spectrace/manage.py agent_claim <task-id> --agent <agent-id>
python spectrace/manage.py agent_start <task-id> --agent <agent-id>
```

### On Agent Submit

```
python spectrace/manage.py agent_submit <task-id> --agent <agent-id> --commit-sha <sha>
```

### On Review

```
python spectrace/manage.py agent_review <task-id> --reviewer <agent-id> --decision approved
```

### On Merge

```
python spectrace/manage.py agent_merge <task-id>
lore remember "Task <task-id> merged: <summary>" --project <project>
```

## Lore Integration (Minimal)

### Decision Capture

Trigger: Merge completion

```
lore remember "SpecTrace task <id> merged: <summary>" --project <project>
```

### Failure Capture

Trigger: agent failure or repeated command failure

```
lore fail ToolError "<task-id> failed: <summary>" --tool ov
```

## Data Contract for Agent Overlays

Overstory injects task metadata into the agent overlay:

```
task_id: <SpecTrace external_id>
title: <title>
description: <description>
done_when: <list>
scope_in: <list>
scope_out: <list>
spec_ref: <link or path>
```

## Responsibility Split

- SpecTrace: authoritative task state + review workflow.
- Overstory: execution, concurrency, and merge automation.
- Lore: durable memory of decisions and failures.
- Praxis: synthesis view (queue, health, blockers).

## Failure Modes

- SpecTrace unavailable: Overstory continues, but logs failure and retries sync.
- Merge succeeds but Lore capture fails: record a single failure in Lore.

## Rollout Plan

1. Phase 1: Overstory reads SpecTrace tasks and writes lifecycle state.
2. Phase 2: Lore write-through on merge and failure.
3. Phase 3: Optional Praxis augmentation with Overstory telemetry.

## Open Questions

- Use SpecTrace API or direct DB access for task reads?
- Reviewer role handled by Overstory reviewer agent or human?
- Should Overstory reflect SpecTrace lease expiration semantics?
