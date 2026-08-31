# Sequential-gated loop (workflow archetype, `shape: sequential-gated`)

The SKILL.md policy binds throughout. Facts live: `status.json` (your single
runtime surface — `plan` is design-derived, everything else is live state) plus
design.yaml / contract.yaml for machinery and the problem.

## Step 1 — load the ledger (this IS resume)

- **Fresh** (`current_task == null`, all `pending`): read the contract + any plan
  docs under `docs/team-forge/<team>/`, set `status.json.current_plan`, set
  `current_task` to the first task with satisfied `depends_on`.
- **Resume**: first task with `status != done`; re-run its `gate_set` if it was
  mid-flight. The two files are the whole state — respawn only a configured
  monitor teammate, nothing else.

Refresh the dashboard (per SKILL.md Observability).

## Step 2 — the task/gate loop

For each task in `depends_on` order, inline by default (dispatch per SKILL.md):

1. **design-before-code** — short DRY/SOLID pass; reject a design that
   re-introduces a copy; non-trivial → write it to
   `artifacts/<task-slug>/<subject>-design-<YYYY-MM-DD>.md`.
2. **implement** — honor the task's `dispatch:` (`inline` default / `worker` /
   `fresh_session` — see SKILL.md's dispatch table + handoff box).
3. **gate** — run the task's `gate_set` (from `status.json.plan.gates`, scaled to
   `blast_radius`). **Never advance on red** — fix in place and re-gate. A gate
   named in `plan.gate_backing` with `promoted: false` has no backing skill:
   it **fails closed**. Say so and hand off — never quietly skip it.
4. **commit** on the integration branch — message names the work, never the ID.
5. **ledger** — per-task fields (`status: done`, `gate_status`, `commit`, a
   `task_completed` event) AND the rollups the panels read: `current_task` ← next
   eligible, `pr_url`, `budget`/spend (`head_sha` derives itself). Refresh the
   dashboard; a summary panel that didn't move = a stale rollup, not a render bug.
6. **loop** to the next task whose `depends_on` are all `done`.

## Step 3 — fan-out bursts

Only at genuine N-way points (per the design's `fan_out` declarations): parallel
build over independent tasks, or verification fan-out (M facet-maps + K
adversarial verdicts → certification doc under `artifacts/<task-slug>/`). Use the
Workflow tool — never a hand-rolled loop of single dispatches; collapse back to
this loop after.

## Step 4 — close

Per SKILL.md Close: run every `done_when` check, final ledger + dashboard +
summary, hand the branch over, never self-merge.
