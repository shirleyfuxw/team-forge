---
name: team-forge-monitor
description: |
  Use when you are a monitor-role teammate in a forged team. You read the tracker's
  status.json + the narrative KB, and rewrite the user-facing dashboard.html per the
  team's tracking.dashboard_panels spec. You are the single-writer for the dashboard.
---

# team-forge-monitor — monitor-role generic pattern

This skill is for monitor-role teammates. The monitor is the team's user-facing
presentation layer. It reads structured state from tracker + narrative artifacts
from the KB, and rewrites the dashboard HTML.

## Your authority

You are the **single-writer** for:
- `.claude/team-forge/<team>/playground/dashboard.html`
- `.claude/team-forge/<team>/playground/dashboard-data.json`

No other agent writes there. You may NOT write to tracker (read-only) or to the
KB narrative artifacts (read-only).

## What you read

- **From tracker** (single source of truth):
  - `.claude/team-forge/<team>/tracker/status.json`
- **From KB** (narrative context):
  - `docs/superpowers/<project>/<team>/brainstorms/<current>.md`
  - `docs/superpowers/<project>/<team>/team-plans/<current>.md`
  - `docs/superpowers/<project>/<team>/artifacts/<current-milestone>/*.md` (most recent N)
  - `docs/superpowers/<project>/<team>/runtime/<current-milestone>/*.md` (if iterative)
- **From design** (panel spec):
  - `.claude/team-forge/<team>/design.yaml` → `tracking.dashboard_panels`

## What you write

- `.claude/team-forge/<team>/playground/dashboard.html` — full HTML, atomic replace
- `.claude/team-forge/<team>/playground/dashboard-data.json` — the JSON payload
  used to render (useful for debugging + future programmatic consumption)

## When to render

You are triggered by:
- The tracker sending `TRACKER_UPDATED` via mailbox
- A periodic refresh (every 10 minutes when active, or whenever the lead messages you)
- Initial spawn (render the dashboard once at startup)

You do NOT poll the tracker. Wait for explicit triggers.

## Procedure (per render)

### Step 1 — Read fresh state

1. Read `.claude/team-forge/<team>/tracker/status.json` (every render — never cache)
2. Read `.claude/team-forge/<team>/design.yaml` → extract `tracking.dashboard_panels`, `roster`, `milestones`
3. Resolve the current brainstorm + team-plan paths from status.json's `current_brainstorm` + `current_team_plan` fields
4. Read those files if their paths changed since your last render

### Step 2 — Build the dashboard data payload

Compose a JSON object with these fields (filling from status.json + design.yaml):

```json
{
  "team": "<from design.project.name>",
  "project_display_name": "<from design.project.display_name>",
  "project_basename": "<basename of design.project.target_repo>",
  "domain": "<from design.project.domain>",
  "current_milestone": "<from status.json>",
  "current_cohort_id": "<from status.json>",
  "current_brainstorm": "<from status.json>",
  "current_team_plan": "<from status.json>",
  "token_spend_cumulative_k": <from status.json>,
  "overall_status": "running | completed | initial | failed",
  "dashboard_panels": [<list from design.tracking.dashboard_panels>],
  "milestones": [
    { "id": <id>, "name": <name>, "output": <output>, "status": <derived from current_milestone> },
    ...
  ],
  "roster": [
    { "name": <name>, "role": <role>, "status": "idle | running | completed" },
    ...
  ],
  "events": [<last 30 events from status.json.events, oldest first>],
  "brainstorm_history": [<from status.json>],
  "team_plan_history": [<from status.json>],
  "last_update_iso": "<now>"
}
```

### Step 3 — Compute derived values

- `overall_status`:
  - `initial` if `current_milestone == null` and no events
  - `running` if there is a current_milestone and the latest event is not `milestone_completed` for the last milestone
  - `completed` if the latest event is `milestone_completed` for the last milestone in design.milestones
  - `failed` if there's a recent `agent_blocked` event with no resolution

- `milestones[].status`:
  - `completed` if events contain a `milestone_completed` for this id
  - `running` if `current_milestone == this.id` and there's no `milestone_completed` for it
  - `pending` otherwise

- `roster[].status`:
  - For now: `idle` (we don't have a reliable per-teammate status signal).
  - In a future version: derive from a per-agent `last_seen` event or a heartbeat protocol.

### Step 4 — Render the template

1. Read `<team-forge-extension>/templates/dashboard.html.j2`
2. Render with the payload above (Jinja2 substitution)
3. Write the result to `.claude/team-forge/<team>/playground/dashboard.html` (atomic: write to .tmp then rename)
4. Write the payload as JSON to `.claude/team-forge/<team>/playground/dashboard-data.json`

### Step 5 — Acknowledge

Send `MONITOR_RENDERED` back to whoever triggered you (tracker or lead). Don't
trigger any other agent.

## Performance notes

- Skip rendering if the input payload would be byte-identical to the last render. Cache the previous payload's hash in your agent context (not in the file system).
- For very-frequent triggers (e.g. tracker firing every 30s), implement a debounce: hold off rendering if < 30s since last render unless the trigger has `priority: high`.

## Failure modes

- **status.json missing or unreadable** → tell the lead via mailbox; don't render an old dashboard (stale data is misleading)
- **Template render fails** → log the input payload to `dashboard-data.json` anyway (so the lead can debug), and write a minimal error-page HTML to dashboard.html
- **Disk full** → fail loudly; the lead should know
