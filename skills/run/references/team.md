# Agent-team loop (`archetype: team`)

The SKILL.md policy binds throughout. Requires
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and an agent-teams-capable Claude Code —
if absent, stop and tell the user.

## Step 1 — adopt the lead role

You are the orchestrator named in `design.yaml.roster`. You manage the shared
task list (`Task*` tools — native to the session's team, never a hand-managed
path), dispatch teammates via `SendMessage`, arbitrate verifier verdicts, and
decide milestone progression with the user at declared go/no-go gates only —
between gates, work toward `done_when` without idling.

## Step 2 — bootstrap vs rehydrate

Read `tracker/status.json`: missing or empty state → **bootstrap**; else →
**rehydrate** (invoke `team-forge:rehydrate` — it recovers state, re-reads the
contract + current plan + recent artifacts, respawns the roster with context).

Bootstrap: read design.yaml + the contract + the current plan doc; spawn roster
per `rehydrate.respawn_order`, each with a **scoped brief** (role, team, its task,
the exact artifacts — never "go read the KB"; provider outage → one tier down);
set `current_milestone` ← first id, pointers, log `milestone_started`.

## Step 3 — coordinate

- Scope shifts → `team-forge:contract` (revise the contract; it re-syncs
  `goal_directive`). Machinery changes (roster/gates) → `team-forge:design`.
- Standing work/verify teammates have NO per-agent memory (`memory:` is ignored
  on the teammate path) — their durable context is the KB + shared task list;
  keep both current. Dispatched advise-role agents self-curate their own memory.
- Milestone done (go/no-go met, verifier verdicts in) → `milestone_completed`
  event, advance `current_milestone`, refresh the dashboard.

## Step 4 — close

Per SKILL.md Close, plus: shut down each teammate before `team-forge:teardown`.
