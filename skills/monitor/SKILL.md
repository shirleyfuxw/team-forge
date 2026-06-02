---
name: team-forge:monitor
description: |
  Use when you are a monitor-role teammate. You read the tracker's status.json +
  the narrative KB, and rewrite the user-facing dashboard.html per the team's
  tracking.dashboard_panels spec. Single-writer for the dashboard files.
---

# team-forge:monitor — monitor-role pattern

This skill is for monitor-role teammates. The monitor reads structured state
from tracker + narrative artifacts from the KB, and rewrites the dashboard HTML.

The dashboard template is **logic-free** — uses `{{VAR}}` substitution plus
named placeholder blocks (`{{PANELS_HTML}}`, `{{EVENTS_HTML}}`) that this skill
fills procedurally.

## Your authority

You are the **single-writer** for:
- `.claude/team-forge/<team>/playground/dashboard.html`
- `.claude/team-forge/<team>/playground/dashboard-data.json`

You may NOT write to tracker (read-only) or KB narrative artifacts (read-only).

## What you read

- `.claude/team-forge/<team>/tracker/status.json` (every render, never cache)
- `.claude/team-forge/<team>/design.yaml` (for `tracking.dashboard_panels`, `roster`, `milestones`)
- `docs/superpowers/<project>/<team>/brainstorms/<current>.md` (path from status.json)
- `docs/superpowers/<project>/<team>/team-plans/<current>.md`
- `docs/superpowers/<project>/<team>/artifacts/<current-milestone>/*.md` (recent N)
- `docs/superpowers/<project>/<team>/runtime/<current-milestone>/*.md` (if iterative)
- The dashboard template at `<team-forge-extension>/templates/dashboard.html.j2`

## What you write

- `dashboard.html` — full HTML, atomic replace
- `dashboard-data.json` — the JSON payload used to render (debug aid)

## When to render

You are triggered by:
- The tracker sending `TRACKER_UPDATED` via mailbox
- The lead requesting a refresh
- Initial spawn (render once at startup)

Do NOT poll. Wait for explicit triggers.

## Procedure (per render)

### Step 1 — Read fresh state

1. Read `tracker/status.json`
2. Read `design.yaml`: extract `tracking.dashboard_panels`, `roster`, `milestones`
3. From status.json's `current_brainstorm` + `current_team_plan` paths, resolve the actual files

### Step 2 — Build the dashboard data payload

Compose a flat JSON dictionary (this becomes dashboard-data.json):

```json
{
  "team": "<from design.project.name>",
  "project_display_name": "<from design.project.display_name>",
  "project_basename": "<from design.project.target_repo_basename>",
  "domain": "<from design.project.domain>",
  "current_milestone": "<from status.json>",
  "current_cohort_id": "<from status.json>",
  "current_brainstorm": "<from status.json>",
  "current_team_plan": "<from status.json>",
  "token_spend_cumulative_k": <from status.json>,
  "overall_status": "<computed: initial|running|completed|failed>",
  "last_update_iso": "<now>",
  "dashboard_panels": [<from design.tracking.dashboard_panels>],
  "milestones": [<from design.milestones, with computed status>],
  "roster": [<from design.roster, with computed status>],
  "events": [<last 30 from status.json.events>]
}
```

Derived values:
- `overall_status`:
  - `initial` if `current_milestone == null` and no events
  - `running` if `current_milestone != null` and last event ≠ `milestone_completed` for the final milestone
  - `completed` if last event is `milestone_completed` for the final milestone
  - `failed` if a recent `agent_blocked` event has no resolution
- `milestones[].status`: `completed` if events contain matching `milestone_completed`; `running` if `current_milestone == this.id`; else `pending`
- `roster[].status`: `idle` (no per-teammate signal yet; future: derive from heartbeats)

### Step 3 — Render the template

Read `templates/dashboard.html.j2`. Perform substitution:

**Simple substitutions** (top-of-template + footer):
- `{{team}}`, `{{project_display_name}}`, `{{project_basename}}`, `{{domain}}` from payload
- `{{current_milestone}}` → payload value (or `—` if null)
- `{{current_cohort_id}}` → payload value (or `—` if null)
- `{{token_spend_cumulative_k}}` → payload value
- `{{overall_status}}` → payload value
- `{{last_update_iso}}` → payload value

**Placeholder blocks:**

#### `{{PANELS_HTML}}`

For each panel in `payload.dashboard_panels`, build a `<div class="panel">` and concatenate:

- `milestone_timeline`:
  ```html
  <div class="panel">
    <div class="panel-title">Milestone timeline</div>
    <div class="panel-intro">Project milestones with status pills.</div>
    <div class="timeline">
      <!-- one row per payload.milestones[] -->
      <div class="milestone-row">
        <div class="milestone-label"><MILESTONE.id></div>
        <div class="milestone-body">
          <div class="ms-name"><MILESTONE.name> <span class="pill <STATUS>"><STATUS></span></div>
          <div class="ms-desc"><MILESTONE.output></div>
        </div>
      </div>
    </div>
  </div>
  ```

- `team_roster_and_status`:
  ```html
  <div class="panel">
    <div class="panel-title">Team roster</div>
    <div class="panel-intro"><N> teammates.</div>
    <table class="roster-table">
      <!-- one row per payload.roster[] -->
      <tr>
        <td class="agent-name"><AGENT.name></td>
        <td><span class="role-tag <ROLE>"><ROLE></span></td>
        <td><span class="pill <STATUS>"><STATUS></span></td>
      </tr>
    </table>
  </div>
  ```

- `current_pointers`:
  ```html
  <div class="panel">
    <div class="panel-title">Current pointers</div>
    <div style="font-size: 13px; line-height: 1.7;">
      <div><span style="color:var(--gray-500)">Brainstorm:</span> <code><CURRENT_BRAINSTORM></code></div>
      <div><span style="color:var(--gray-500)">Team plan:</span> <code><CURRENT_TEAM_PLAN></code></div>
    </div>
  </div>
  ```

- Any other panel: emit empty-state placeholder:
  ```html
  <div class="panel">
    <div class="panel-title"><PANEL-NAME-TITLE-CASED></div>
    <div class="empty-state">Awaiting data. Monitor populates this from tracker events.</div>
  </div>
  ```

#### `{{EVENTS_HTML}}`

If `payload.events` is empty:
```html
<div class="empty-state">No events yet. The team is just starting.</div>
```

Otherwise (events most-recent-first):
```html
<div style="font-size: 12px; max-height: 480px; overflow-y: auto;">
  <!-- one row per event, newest first -->
  <div class="event-row">
    <div class="event-meta"><EVENT.ts> · <EVENT.actor></div>
    <div style="margin-top:2px"><strong><EVENT.kind></strong> — <EVENT.summary></div>
  </div>
</div>
```

### Step 4 — Write atomically

1. Write rendered HTML to a temp file `<dashboard.html>.tmp`
2. `mv` it over the real `dashboard.html`
3. Write the payload JSON to `dashboard-data.json` (overwrite is fine)

### Step 5 — Acknowledge

Send `MONITOR_RENDERED` to whoever triggered you (tracker or lead).

## Performance notes

- Skip rendering if the input payload's hash matches the last render's. Cache that hash in your agent context.
- Implement a 30-second debounce for rapid-fire triggers unless flagged `priority: high`.

## Failure modes

- **status.json missing/unreadable** → tell the lead via mailbox; do NOT render an old dashboard (stale = misleading)
- **Template render fails** → write the payload to `dashboard-data.json` for debugging; write a minimal error-page HTML to dashboard.html
- **Disk full** → fail loudly to the lead
