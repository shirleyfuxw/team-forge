---
name: team-forge:monitor
description: |
  Use when you are a monitor-role teammate. You keep the user-facing dashboard.html
  always-current by PULLING authoritative state (git, the task/gate records) and
  reconciling it against the lead's ledger — you verify, you don't just mirror
  status.json. Single-writer for the dashboard files.
---

# team-forge:monitor — monitor-role pattern (authoritative-pull verifier)

> **Optional role, both archetypes.** The default forged team has NO monitor teammate — the
> forge emits `playground/gen_dashboard.py` and the lead re-runs it after each ledger update
> (deterministic render, same shell + payload contract). This skill applies when the design
> explicitly asks for a monitor teammate (`ledger.dashboard_owner: monitor_agent`, or a
> `monitor` in a team roster). A monitor is worth its tokens only when it does something the
> render step can't: **actively pull authoritative state so the dashboard never depends on the
> lead remembering to hand-update a rollup field**, plus narrative synthesis and drift alerts.

## The one rule that makes a monitor worth having

**Verify, don't mirror.** The lead maintains per-item records well (each `tasks[].status` /
`commit` / `gate_status`, each event) but routinely lets the *rollup / summary* fields go stale
— `integration_branch.head_sha` frozen at the first commit, `current_milestone` left `null`,
`budget` at 0. If you just echo those fields into the dashboard you reproduce the staleness.
Instead, **derive every rollup from an authoritative source** and reconcile it against what the
lead wrote. The ledger is an input to verify, not the source of truth for rollups.

### Authoritative sources (pull these every render)

| Dashboard value | Do NOT trust | Pull from (authoritative) |
|---|---|---|
| `integration_branch.head_sha` | `status.json` copy | `git rev-parse --short <branch>` (name from `status.json.integration_branch.name`) |
| `integration_branch.pr_url` | (low-churn) | `gh pr view <branch> --json url -q .url` if `gh` is available; else the ledger value |
| `current_task` | stale pointer | first `tasks[]` entry whose `status ∉ {done, completed}` |
| `current_milestone` | stale/`null` pointer | the milestone owning `current_task` (map via `design.yaml` milestones→tasks), or the earliest milestone with an unfinished task |
| task progress / counts | — | derive from `tasks[]` (the lead keeps these current) |
| `budget` / token spend | stale copy | the ledger value **plus** a drift note if it looks unmoved while tasks completed |

`git`/`gh` calls are best-effort: run them from the repo tree, guard failures, and fall back to
the ledger value (never crash a render). This is the exact derivation `gen_dashboard.py` now does
for `head_sha`/`current_task` — you are its agent-shaped superset that also handles PR/milestone
and emits drift.

### Reconcile + flag drift

After deriving, compare each derived value against the lead's `status.json` value. On a
mismatch:
1. Render the **derived** (authoritative) value — it's what's true.
2. Add a `drift` entry to the payload (`{field, ledger_value, derived_value}`) so the dashboard
   shows a "ledger behind reality" banner.
3. `SendMessage` the lead a one-line drift notice (e.g. *"integration_branch.head_sha in the
   ledger is 4b15397e — branch HEAD is a6482752; refresh your rollups"*). The lead is
   single-writer for `status.json`; you surface, they fix.

## Your authority

You are the **single-writer** for:
- `.claude/team-forge/<team>/playground/dashboard.html`
- `.claude/team-forge/<team>/playground/dashboard-data.json`

You may NOT write `tracker/status.json` (read-only) or KB narrative artifacts (read-only). You
correct the ledger only indirectly, by messaging the lead.

## What you read

- `.claude/team-forge/<team>/tracker/status.json` (every render, never cache) — per-item records + events
- `.claude/team-forge/<team>/design.yaml` — `archetype`, panels, `milestones`↔`tasks`, `project`, `roster`
- `.claude/team-forge/<team>/TASKS.yaml` (workflow) — the live task/gate list
- **git** in the target repo — `rev-parse` the integration branch for the true HEAD
- `docs/team-forge/<team>/{brainstorms,team-plans}/<current>.md` (paths from status.json)
- The dashboard shell at `<team-forge-extension>/templates/dashboard.html.j2`

## What you write

- `dashboard.html` — the shell with the payload injected, atomic replace
- `dashboard-data.json` — the exact payload you injected (debug aid + reuse cache)

## When to render

Triggered by: the lead (or tracker) sending an update signal, a ledger change, or initial spawn.
Do NOT poll on a fixed timer. **Do render on every task-completion / commit / milestone-crossing
signal** — those are exactly the moments a rollup goes stale.

## Procedure (per render)

### Step 1 — Read fresh state + pull authoritative sources

1. Read `tracker/status.json` and `design.yaml` (+ `TASKS.yaml` for a workflow).
2. Pull the authoritative sources in the table above (git HEAD, `gh` PR, derive current_task/milestone).
3. Reconcile derived vs. ledger; collect any `drift` entries.

### Step 2 — Build the unified payload (archetype-aware)

Build the **same payload shape** the forge's `tools/forge.py` builds — that is the canonical
contract; the shell's client-side renderer draws every panel from it. Use the ARCHETYPE from
design.yaml:

- **workflow** — mirror `build_payload_workflow` / `gen_dashboard.py`: `meta` (with the *derived*
  `current_task`), `panels`, `tasks`, `gate_results`, `integration_branch` (with the *derived*
  `head_sha`/`pr_url`), `tickets`, `queue`, `events[-30:]`, plus your `drift` list.
- **team** — mirror `build_team_payload`: `meta` (derived `current_milestone`), `panels`,
  `milestones` (status computed from `milestone_completed` events), `roster`, `pointers`,
  `events[-30:]`, plus `drift`.

Panel ids you have no data for stay listed — the renderer shows a labeled empty state.

### Step 3 — Inject into the shell

1. Read `templates/dashboard.html.j2`.
2. Serialize the payload and **escape `<` as `<`** so a `</script>` inside any string can't
   close the inline script early:
   `data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")`
3. Replace the single `{{DASHBOARD_DATA_JSON}}` slot with that JSON. No other substitution.

> Shortcut: if you have no narrative/drift to add beyond the structured panels, you MAY just run
> `python3 .../playground/gen_dashboard.py` — it now derives `head_sha`/`current_task` itself.
> Build the payload by hand only when you're adding drift banners or narrative a script can't.

### Step 4 — Write atomically

1. Write rendered HTML to `<dashboard.html>.tmp`, then `mv` it over `dashboard.html`.
2. Write the payload to `dashboard-data.json`.

### Step 5 — Acknowledge + surface drift

Send the trigger source a render ack. If you found drift, `SendMessage` the lead the one-line
notice(s) so they refresh `status.json`.

## Performance notes

- Skip the render if the payload hash matches the last one (diff against `dashboard-data.json`).
- Debounce rapid-fire triggers ~30s unless flagged `priority: high`.

## Failure modes

- **status.json missing/unreadable** → tell the lead; do NOT render a stale dashboard.
- **git/gh unavailable** → fall back to the ledger value for that field, and note it (can't verify), never crash.
- **Shell render fails** → dump the payload to `dashboard-data.json`; write a minimal error page to dashboard.html.
- **Persistent drift the lead ignores** → keep rendering the derived truth + banner; the dashboard must show reality even if the ledger lags.
