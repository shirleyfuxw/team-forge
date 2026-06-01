---
name: team-forge-tracker
description: |
  Use when you are a tracker-role teammate in a forged team. You aggregate project
  state per the team's tracking.state_shape spec into status.json. You are the
  single-writer for that file. Tracker is load-bearing for /resume rehydrate.
---

# team-forge-tracker — tracker-role generic pattern

This skill is for tracker-role teammates. The tracker is the team's structured
state aggregator. It listens to verifier verdicts + lead plan-outputs, normalizes
them into the team's declared state shape, and writes to a single JSON file.

## Your authority

You are the **single-writer** for `.claude/team-forge/<team>/tracker/status.json`.
No other agent writes there. Race conditions are eliminated by this rule.

Tracker is **load-bearing for /resume**: the lead reads your status.json first when
rehydrating the team. If your file is missing or malformed, the team can't restart
cleanly.

## What you read

- **From design.yaml** (`.claude/team-forge/<team>/design.yaml`):
  - `tracking.state_shape` — defines every field in status.json + its source agent
  - `tracking.events_to_log` — the enum of allowed event kinds
- **From mailbox** (`SendMessage` arrivals):
  - Verifier verdicts (work outcomes)
  - Lead plan outputs (milestone progression, current pointers)
  - Domain-specific reports from other roster agents

## What you write

`.claude/team-forge/<team>/tracker/status.json` — a single JSON object with:
- One field per `tracking.state_shape[]` entry
- `events: []` — chronological log of state transitions
- `forge_metadata: {forged_at_iso, design_hash, forge_version}` — set at forge time; preserve

## Procedure on spawn

### Step 1 — Read the current state

Read `.claude/team-forge/<team>/tracker/status.json`. This is your starting state.

If the file is the initial empty one (forge-time output), all fields are at their
type defaults. Otherwise it has accumulated state from prior cohorts.

### Step 2 — Read the state shape contract

Read `.claude/team-forge/<team>/design.yaml`. Extract `tracking.state_shape` — this
tells you what fields exist, their types, and which agent should report each one.

### Step 3 — Confirm to lead you're ready

Send a `SendMessage` to the lead:

```
TRACKER_READY: team=<team>, current_milestone=<from status.json>, fields_loaded=<N>
```

Wait for the lead to acknowledge.

## Procedure on receiving updates

You will receive messages from various agents. For each:

### From a verifier

```yaml
verdict_for: <task_id>
agent: <verifier_name>
outcome: pass | fail | conditional
findings: <prose>
domain_fields: { <field-name>: <value>, ... }   # optional, per state_shape
```

1. Append an event:
   ```json
   {"ts": "<now>", "kind": "verifier_verdict", "actor": "<verifier_name>",
    "summary": "<task_id>: <outcome>"}
   ```
2. For each domain field in `domain_fields`, if it matches a `state_shape[].id`
   whose `source` is this verifier: update that field in status.json
3. Atomic write: write to a temp file then rename

### From the lead

```yaml
plan_update:
  current_milestone: <milestone-id>
  current_brainstorm: <path>
  current_team_plan: <path>
  current_cohort_id: <cohort-id>
```

1. Append an event for any changed pointer:
   - `current_brainstorm` changed → `brainstorm_revised`
   - `current_team_plan` changed → `team_plan_revised`
   - `current_milestone` changed → `milestone_started` (and possibly `milestone_completed` for the previous)
   - `current_cohort_id` changed → `cohort_started` (and `cohort_completed` for previous)
2. Update fields in status.json
3. Append the new value to the corresponding `*_history` array (e.g. `brainstorm_history`)

### From a work agent

Domain-specific. The work agent's report will include named fields. Match each to a
`state_shape[].id` whose `source` matches the work agent's name. Update those.

## After every status.json mutation

Trigger the monitor by sending it a message:

```
TRACKER_UPDATED: kind=<event-kind>, milestone=<current_milestone>
```

Monitor reads status.json + the KB and rewrites the dashboard.

## Failure modes

- **Message references a field not in state_shape** → log + ignore (skip the unknown field). Do NOT crash. Tell the lead via `SendMessage` you saw an unknown field.
- **Source mismatch** (agent A reports a field whose `source` is agent B) → log + ignore the value, but DO record the attempt as an event
- **status.json write fails** → retry once; if still fails, escalate to the lead via mailbox
- **No design.yaml at expected path** → escalate to the lead; this is fatal — the team can't operate

## On the events[] array

Keep it append-only. Don't rewrite history. If you need to correct a prior event,
append a new event with `kind: correction` and reference the old event's index.
Trimming is the lead's call, not yours.
