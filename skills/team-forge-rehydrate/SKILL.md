---
name: team-forge-rehydrate
description: |
  Use when the lead is being re-launched on /resume and needs to restore the agent
  team from durable state. Reads tracker, brainstorm, team-plan, artifacts, then
  respawns all teammates with full context. Invoked by the team-launcher skill.
---

# team-forge-rehydrate — runtime /resume protocol

When the lead session is `/resume`'d (or a fresh session adopts the lead role for
an already-forged team), agent-team teammates are GONE — they evaporated when the
prior session ended (per Claude Code's documented agent-teams limitation).

The lead's job: respawn the team from durable state.

## When to use

Invoked by the team-launcher skill (`/<team>-team`) when bootstrap-detection finds:
- `.claude/team-forge/<team>/tracker/status.json` exists AND
- It has non-trivial state (`current_milestone != null` OR `cohort_count > 0`)

Also invoked if the user explicitly asks to rehydrate.

## Inputs

- The team name (you adopted it via `/<team>-team`)
- The target_repo (current working directory)

## Procedure

### Step 1 — Read tracker state

Read `.claude/team-forge/<team>/tracker/status.json` fully.

Note in particular:
- `current_milestone`
- `current_brainstorm` (path)
- `current_team_plan` (path)
- `current_cohort_id`
- `brainstorm_history`, `team_plan_history`
- Domain-specific state fields (varies per project — see design.yaml's `tracking.state_shape`)
- `events` (most-recent 20 — useful for context)

### Step 2 — Read the project KB

Read these in order:
1. `docs/superpowers/<project_basename>/<team>/brainstorms/<current_brainstorm>` — full project understanding
2. `docs/superpowers/<project_basename>/<team>/team-plans/<current_team_plan>` — full delegation plan
3. `docs/superpowers/<project_basename>/<team>/artifacts/<current_milestone>/` — list recent files, read the most recent 3 verifier walkthroughs + section conclusions
4. `docs/superpowers/<project_basename>/<team>/runtime/<current_milestone>/` — if exists, read the most recent per-iteration plan

### Step 3 — Read the design contract

Read `.claude/team-forge/<team>/design.yaml`. Note:
- The full roster (you need to spawn all of them)
- `rehydrate.respawn_order` (canonical order)
- Each teammate's role + skills + memory authority

### Step 4 — Respawn teammates in order

For each entry in `rehydrate.respawn_order`:

1. Find the matching roster entry in `design.yaml.roster`
2. Spawn a teammate using that subagent type (the agent .md was forged at Phase 4)
3. The spawn prompt should include:
   - Their role (canonical)
   - Their team name
   - A pointer to the runtime hub: `.claude/team-forge/<team>/`
   - A pointer to the KB: `docs/superpowers/<project_basename>/<team>/`
   - A summary of where work was when the prior session ended (1–3 sentences from `events`)
   - For work-role teammates with an active task in `~/.claude/tasks/<team>/`: their assigned task id

**Tracker is FIRST** (per respawn_order convention). It reads its own status.json on
spawn and reports back any inconsistencies. If tracker reports an issue, **stop and
tell the user** before spawning the rest.

### Step 5 — Verify task list state

Read `~/.claude/tasks/<team>/`. The task list is native to agent-teams — it should
still be there from the prior session. Verify:
- Pending tasks still pending (no orphans)
- In-progress tasks: who was assigned? Are those teammates spawned now?
- Completed tasks: count matches events[]

If task list is gone or corrupt, ask the user whether to:
- Reconstruct from tracker events + lead's plan
- Abort and let the user resolve manually

### Step 6 — Log the rehydrate event

Tell the tracker (via mailbox) to append a `rehydrate` event:

```json
{
  "ts": "<now-iso>",
  "kind": "rehydrate",
  "actor": "<lead-name>",
  "summary": "Respawned <N> teammates; resumed at <current_milestone>"
}
```

### Step 7 — Trigger monitor

Tell the monitor (via mailbox) to refresh the dashboard. It will pick up the new
event and update `playground/dashboard.html`.

### Step 8 — Report status to user

Tell the user:
- The team has been rehydrated
- Current milestone, current cohort/iteration if applicable
- Active threads / in-progress tasks
- What you (the lead) intend to do next

Wait for user confirmation before continuing work.

## Failure modes

- **status.json corrupted** → abort, tell user; suggest restoring from git if committed
- **A roster teammate fails to spawn** → log the failure, tell user; offer to skip-and-degrade or abort
- **KB files referenced in status.json are missing** → abort; suggest checking git for deleted files
- **Task list missing** → ask user before reconstructing
