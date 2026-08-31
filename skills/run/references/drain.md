# Parallel-drain loop (workflow archetype, `shape: parallel-drain`) — one cycle

The SKILL.md policy binds throughout. `design.recurring` decides the outer loop:
recurring → the schedule fires the next cycle, this runtime runs ONE cycle and
exits (unattended: plan-gate items HOLD, per-item gates mandatory); absent →
one-shot, drain once and close.

## Step 1 — open the cycle (this IS resume)

Read `status.json` — `plan.queue` + `plan.gates` for the shape of the work, the
live keys for where you left off. Stamp `current_cycle_id` +
`cycle_box_deadline` from the box. Carry-overs (`in_review` items in
`status.json.tickets[]`) re-attach before new triage. Log `cycle_started`;
refresh the dashboard.

## Step 2 — triage

1. Run `queue.eligibility` → eligible set.
2. Apply `queue.triage`: per-item `route` + `blast_radius` + `gate_set`; write the
   partition to `status.json.tickets[]` + `queue_*` counts; log
   `ticket_triaged`/`ticket_routed`.
3. `full-drain` → Step 3. `plan-gate` = the risky set — HOLDS for human approval
   (auto-approve nothing, especially unattended).

## Step 3 — drain in waves

Two or more independent items → the **Workflow tool's `pipeline(items, drain,
gate)`** in waves of ≤ `queue.wave_size` — never a sequential for-loop of
dispatches (loses concurrency + `/workflows` visibility). A single-item wave →
one inline worker dispatch. Per item:

- **drain** — dispatch the worker profile (own worktree, scoped brief; memory
  compounds; provider outage → one tier down). Self-modifying items (`.claude/**`
  config) can't be worker-drained: pull from the wave → `fresh_session` handoff
  (SKILL.md), drain the rest.
- **gate** — the item's `gate_set`; never PR on red.
- green → PR against the integration branch; `stage: pr_ready`.

Items are independent — no peer coordination; you own the wave + ledger. The
worktree boundary (SKILL.md) applies per live dispatch.

**Box freeze:** past `cycle_box_deadline`, no new wave; in-flight items finish
their current iteration, checkpoint the PR, carry as `in_review`. Log
`cycle_box_hit`.

## Step 4 — report + persist (+ rotate)

`status.json` thin: per-item `stage`/`pr_url`/`gate_status`, `queue_*` counts,
`budget`. Refresh the dashboard. Cycle report under `artifacts/<cycle-id>/`
(dated, descriptive). Rotate detail to `runtime/<cycle-id>/`; log
`cycle_completed`. Re-plan per SKILL.md if the routing predicate or gates proved
wrong. One-shot → proceed to SKILL.md Close (including teardown after review);
recurring → exit the cycle, the schedule owns the rest.
