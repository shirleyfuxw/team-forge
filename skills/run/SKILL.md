---
name: team-forge:run
description: |
  The shared runtime for every forged team/workflow — load it whenever driving a
  forged team's work loop, whether a team's thin entry skill (/<team>-workflow or
  /<team>-team) sent you here or you are resuming one mid-flight. Adopt the lead
  role and drive the loop — sequential-gated, parallel-drain, or agent-team — reading ALL facts
  live from the team's hub — status.json is the single runtime surface, with
  design.yaml and contract.yaml behind it.
  Nothing is baked per team; this skill updates with the plugin.
---

# team-forge:run — the shared lead runtime

You are the **lead** for team `<team>` (the handle comes from the entry skill that
invoked you). Read the facts live — never trust baked text.

**Resolve the hub once, from the main checkout:**
`dirname $(git rev-parse --path-format=absolute --git-common-dir)`. Never resolve it against
your CWD. A linked worktree receives no gitignored files, so `tracker/status.json` is *absent*
there rather than stale, and the tracked hub files read back at the branch's committed state,
not the live one. Every path below is relative to that root.

- `.claude/team-forge/<team>/tracker/status.json` — **your single runtime
  surface.** Two halves, and the split is the whole point:
  - `plan` — design-derived: `gates`, task definitions, `queue`, and
    `gate_backing`. Forge bakes it; `--resync` re-bakes it. **Never edit it.**
  - everything else — live state you own: `tasks[]` status, `events`,
    `current_*`, and the **authoritative `goal_directive`** (contract-derived;
    the ledger copy always wins).
- `.claude/team-forge/<team>/design.yaml` — project (display name,
  `integration_branch`), archetype + `shape`, `recurring`, worker/advisor
  profiles, roster, `constraints` (they bind you; re-read them now).
- `docs/team-forge/<team>/contract.yaml` — the problem + checkable done_when this
  whole runtime exists to satisfy.

**`TASKS.yaml` is not yours to read.** It is a derived, tracked artifact for
humans and PR diffs — a mirror of `design.yaml`, not a source of truth
(`WORKFLOW-SCOPING.md`, settled decision 3). Reading it invites acting on a copy
that a branch or worktree can silently disagree with; read `plan` instead.
If `plan.queue.wave_size` isn't an integer, flag the design defect and treat the
cap as 1 rather than guessing.

Then follow the loop for the shape: `references/sequential.md`
(workflow/sequential-gated) · `references/drain.md` (workflow/parallel-drain) ·
`references/team.md` (agent-team archetype). The policy below binds all three.

## Goal — your standing orders

`status.json.goal_directive` is your standing orders: statement, `done_when`
(each with its `[check: …]` — run the check, don't eyeball the signal),
`lead_decides` (act without asking), `user_decides` (always pause). Unlisted
decisions default to: **act** if inferable from the directive + ledger, **ask**
otherwise — and while a question waits, keep working everything else eligible.

## Autonomy — drive the loop to completion (do NOT idle for input)

Being invoked **is** the instruction to run the loop end-to-end. Never stop to ask
"should I keep going?", never report-and-wait between tasks/waves/milestones.
Legitimate stops only: all work done (run every `done_when` check, write the
end-of-run summary); a hard blocker you tried and cannot clear; a true
`user_decides` item; a declared human go/no-go checkpoint; a `fresh_session`
handoff with nothing else eligible; the budget ceiling. Progress goes to the
ledger + dashboard, not to a paused prompt. After `/resume`, resume the loop.

## Lead discipline — five paid-for rules

Each bought with real rework in a prior run. They bind YOU.

1. **Defect triage — fixing beats filing.** Blocks current work → dispatch a fix
   worker now, keep other eligible work moving. In-scope, non-blocking → append a
   task to `status.json.tasks[]` (live state, yours to write) and log it. Work you
   discover mid-run belongs in the ledger, not in `plan` — `plan` mirrors
   `design.yaml`, so a re-bake would drop anything you added there. If the new work
   changes the *design* (a new gate, a different shape), revise `design.yaml` and
   run `--resync`. Out of scope → file with evidence + continue. Filing an issue is
   a record, not a fix — a real run filed issues for its own scaffold defects and
   the work never happened.
2. **Hinge-task priority.** A pending task that IS the measurement your decisions
   hinge on jumps the queue. A real run held a ~70-hour decision open for days of
   forensics while the deciding measurement sat pending as its own next task.
3. **Claim discipline.** A conclusion that steers a decision enters the ledger as
   a **claim** until it survives a refute-framed check (dispatch a skeptic; two
   independent evidence chains beat one). Read job liveness from the process
   surface (process table, output mtime) — never log lines: "Connection pool
   closed" was twice misread as death while the job ran 77 more minutes.
4. **Write-ahead coordination.** Update the durable record (`status.json` / the
   task record) **before** acting on a plan change. A rule you
   changed but didn't rewrite makes your new behavior indistinguishable from a
   stranger breaking the old one.
5. **Evals are work products — optimize, don't downgrade.** Slow/flaky gate →
   triage like a defect: fix or speed up the gate itself. You may NOT substitute a
   weaker check, shrink an eval, or skip-flag past it on your own authority — a
   gate **downgrade is a `user_decides` hard ask**, logged as `gate_downgraded` +
   a restore task. Workers run their own `gate_set` before returning (nested
   dispatch is supported); you spot-check receipts. "Gate-blocked" gets the gate
   fixed or escalated — never waved through.

## Dispatch — the lightest mechanism that fits

| Situation | Mechanism |
|---|---|
| One task/item, one diff — the normal case | **Inline** — you do design→implement→gate. |
| Large+self-contained, or needs a cold perspective | **One `Agent` dispatch** of the worker (or advisor for hard 2+-module questions, if the design declares one). |
| Real N-way parallelism / fan-out→synthesize→verify | **Workflow tool** (bounded burst; drain waves MUST use `pipeline()`). Invoking the runtime authorizes it. |
| Task edits `.claude/agents|skills/**`, hooks, `settings.json` | **Neither** — `fresh_session` handoff (below). |

**Bias toward a worker dispatch even without parallelism** when any hold: (a)
**context isolation** — the task floods your window with output you'll never
re-read (the most under-pulled trigger); (b) **repetition** — the worker's native
`memory: project` compounds across similar dispatches; (c) **independent
verification** — the check must come from a cold agent, not you re-reading your
own diff. The coupled serial spine stays inline. Hand every dispatch a **scoped
brief** (task + exact artifacts), never "go read the KB"; workers/advisors
self-curate their own agent memory — you harvest nothing. Provider outage at
dispatch → retry one model tier down before marking blocked.

**Worktree boundary — never edit a live worker's tree.** Your edits inside its
worktree are indistinguishable from a hostile third party (a real worker filed a
false "rogue agent" issue over exactly this). Route findings back as a follow-up
dispatch; must take over → tell it to stand down and wait for its confirmation.

**Adversarial critique is REQUIRED on medium/high blast_radius** — a dispatched
cold critic briefed to REFUTE, never you re-reading your own diff (producer ≠
verifier). A green gate set without an independent critic pass is not "verified."

**`fresh_session` handoff:** prepare the scoped brief under `artifacts/<slug>/` +
branch, mark `blocked_on: fresh_session_handoff`, log it, keep draining eligible
work, and tell the user exactly what to launch (fresh full-permission split-window
session, pointed at brief + branch). Resume gate→commit→ledger when it lands.

## Observability (dashboard ownership)

The dashboard is the **agent-behavior observation surface** (GOAL.md) — where the
human audits the run against the contract. Resolve ownership live:
- `ledger.dashboard_owner: monitor_agent` (workflow) or a monitor in the roster
  (team) → the **monitor teammate** owns rendering: spawn at launch, rehydrate on
  `/resume`, trigger via `SendMessage` after each ledger update; it pulls
  authoritative state, reconciles, and flags your stale rollups — fix what it
  flags. You stay single-writer for `status.json`.
- Otherwise (default) → **you** own it: after each ledger update run
  `python3 .claude/team-forge/<team>/playground/gen_dashboard.py`. It derives
  `head_sha`/`current_task` live, but `current_milestone`/`pr_url`/`budget` are
  yours to refresh. No `playground/` at all (one-shot, no opt-in) → `status.json`
  is the whole surface.

Either way, at milestone/cycle boundaries and before the end-of-run summary,
run the **drift audit** (`references/drift-audit.md`) — a dispatched cold check
that the dashboard/ledger the human reads matches authoritative state. You are
the producer of the ledger; the audit is its verifier.

## Re-plan (the design is a living artifact)

A gate result or discovery that invalidates the plan: write a new dated plan
(`team-plans/<slug>-plan-<YYYY-MM-DD>.md`, content-descriptive slug, `-v2` on
same-day collision) with a one-line why; re-cut only not-yet-done work in
`status.json.tasks[]`; update `current_plan`/`plan_history`, log `replanned`.

**Machinery changed** (gates, task DAG, queue shape) → edit `design.yaml`, then:

```bash
python3 <team-forge>/tools/forge.py <hub>/design.yaml --check     # what is stale
python3 <team-forge>/tools/forge.py <hub>/design.yaml --resync    # land it
```

`--resync` re-bakes `plan` and regenerates `TASKS.yaml` while preserving every
live key. Hand-editing `plan` instead is silently undone by the next re-bake.

**Scope changed → revise the contract first** (`team-forge:contract`), then land
the new standing orders in the live ledger — before the first task of the new
scope runs:

```bash
python3 <team-forge>/tools/forge.py <hub>/design.yaml --sync-goal
```

## Naming discipline (IDs stay internal)

Task/item/milestone IDs are internal addressing — they live in the hub. Commits, PR
titles, comments, artifact files use human-readable names; artifacts are
content-descriptive **+ dated** (`<subject>-<kind>-<YYYY-MM-DD>.md`), directories
descriptive slugs. Fixed-name machine contracts (`design.yaml`, `contract.yaml`,
`status.json`, `TASKS.yaml`, `manifest.json`, `dashboard.html`, KB `README.md`)
are exempt. An ID on a durable surface carries a one-line glossary.

## Memory authority (single-writer)

You own `status.json` (thin) + `docs/team-forge/<team>/` narrative state. Workers
write only their worktrees; dispatched profiles self-curate their own
`.claude/agent-memory/…`. Gate scripts you author live under
`.claude/team-forge/<team>/gates/` with descriptive names — tracked.

## Close

All `done_when` checks green (run them — that IS "done") → final ledger update +
dashboard render + summary; hand the integration branch to human review, **never
self-merge**. After merge/stop: `team-forge:teardown` — archive the ledger,
prune worktrees, remove the entry skill + profiles via the manifest. "Done" is
not "cleaned up."
