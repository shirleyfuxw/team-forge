---
name: team-forge:monitor
description: |
  Use when you are a monitor-role teammate. You read the tracker's status.json +
  the narrative KB, and rewrite the user-facing dashboard.html per the team's
  tracking.dashboard_panels spec. Single-writer for the dashboard files.
---

# team-forge:monitor — monitor-role pattern

> **Optional role.** The default forged team has NO monitor teammate — the forge emits
> `playground/gen_dashboard.py` instead, and the lead re-runs it after each status.json
> update (deterministic render, same shell + payload contract). This skill applies only
> when the design.yaml roster explicitly includes a monitor.

This skill is for monitor-role teammates. The monitor reads structured state
from tracker + narrative artifacts from the KB, and rewrites the dashboard HTML.

The dashboard shell (`templates/dashboard.html.j2`) is **self-contained**: it
carries the full design-system CSS and a client-side renderer, and exposes a
**single** slot, `{{DASHBOARD_DATA_JSON}}`. Your whole job each render is to build
one **payload** from state and inject it into that slot. You do **not** hand-build
panel HTML — the shell's renderer draws every panel from the payload. (The workflow
archetype's `gen_dashboard.py` produces the identical payload from the identical
shell; the only difference is that here an agent writes it.)

## Your authority

You are the **single-writer** for:
- `.claude/team-forge/<team>/playground/dashboard.html`
- `.claude/team-forge/<team>/playground/dashboard-data.json`

You may NOT write to tracker (read-only) or KB narrative artifacts (read-only).

## What you read

- `.claude/team-forge/<team>/tracker/status.json` (every render, never cache)
- `.claude/team-forge/<team>/design.yaml` (for `tracking.dashboard_panels`, `roster`, `milestones`, `project`)
- `docs/team-forge/<team>/brainstorms/<current>.md` (path from status.json)
- `docs/team-forge/<team>/team-plans/<current>.md`
- The dashboard shell at `<team-forge-extension>/templates/dashboard.html.j2`

## What you write

- `dashboard.html` — the shell with the payload injected, atomic replace
- `dashboard-data.json` — the exact payload you injected (debug aid + reuse cache)

## When to render

You are triggered by:
- The tracker sending `TRACKER_UPDATED` via mailbox
- The lead requesting a refresh
- Initial spawn (render once at startup)

Do NOT poll. Wait for explicit triggers.

## Procedure (per render)

### Step 1 — Read fresh state

1. Read `tracker/status.json`
2. Read `design.yaml`: extract `project`, `tracking.dashboard_panels`, `roster`, `milestones`
3. Resolve `current_brainstorm` + `current_team_plan` paths from status.json

### Step 2 — Build the unified payload

Compose this nested object (it becomes `dashboard-data.json` verbatim). This is the
**exact same shape** that `tools/forge.py::build_team_payload` produces at forge time —
that function is the canonical reference; keep this in sync with it.

```json
{
  "meta": {
    "team": "<design.project.name>",
    "project_display_name": "<design.project.display_name>",
    "project_basename": "<design.project.target_repo_basename>",
    "domain": "<design.project.domain>",
    "archetype": "team",
    "overall_status": "<computed: initial|running|completed>",
    "current_milestone": "<status.json or null>",
    "current_cohort_id": "<status.json or null>",
    "token_spend_cumulative_k": <status.json or 0>,
    "last_update_iso": "<now, ISO-8601 Z>"
  },
  "panels": [<design.tracking.dashboard_panels, in order>],
  "milestones": [{ "id", "name", "output", "status" }],
  "roster": [{ "name", "role", "status" }],
  "pointers": { "brainstorm": "<current_brainstorm or null>", "team_plan": "<current_team_plan or null>" },
  "events": [<last 30 of status.json.events, oldest→newest>]
}
```

Derived values (these mirror `tools/forge.py::build_team_payload` exactly):
- A milestone is **done** when a `milestone_completed` event names it. Those events SHOULD
  carry a `milestone_id` field (the tracker writes it); if absent, fall back to position —
  with sequential milestones, everything before `current_milestone` is done.
- `milestones[].status`: `completed` if the milestone is done (per above); `running` if
  `current_milestone == this.id`; else `pending`.
- `meta.overall_status`: `initial` if no events; `completed` if the final milestone is done
  (or, lacking `milestone_id`, you are on the final milestone and there are ≥ N
  `milestone_completed` events for N milestones); otherwise `running`.
- `roster[].status`: `idle` (no per-teammate signal yet; future: derive from heartbeats).
- Each event keeps `{ ts, actor, kind, summary }` (milestone events additionally carry
  `milestone_id`). The renderer renders events newest-first and handles empty lists itself —
  pass the list as-is.

Panel ids you don't have data for are fine — list them in `panels` anyway; the renderer
shows a labeled empty-state for any panel it can't fill.

### Step 3 — Inject into the shell

1. Read `templates/dashboard.html.j2`.
2. Serialize the payload to JSON. **Escape `<` as `<`** so a `</script>` inside any
   string field can't close the inline script tag early:
   `data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")`
3. Replace the single `{{DASHBOARD_DATA_JSON}}` slot with that JSON. No other
   substitution — every visible value comes from the payload.

### Step 4 — Write atomically

1. Write the rendered HTML to a temp file `<dashboard.html>.tmp`
2. `mv` it over the real `dashboard.html`
3. Write the payload JSON to `dashboard-data.json` (overwrite is fine)

### Step 5 — Acknowledge

Send `MONITOR_RENDERED` to whoever triggered you (tracker or lead).

## Performance notes

- Skip rendering if the payload's hash matches the last render's. Cache that hash in your
  agent context (or diff against `dashboard-data.json`).
- Implement a 30-second debounce for rapid-fire triggers unless flagged `priority: high`.

## Failure modes

- **status.json missing/unreadable** → tell the lead via mailbox; do NOT render an old dashboard (stale = misleading)
- **Shell render fails** → write the payload to `dashboard-data.json` for debugging; write a minimal error-page HTML to dashboard.html
- **Disk full** → fail loudly to the lead
