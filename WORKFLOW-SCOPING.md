# team-forge — workflow-archetype scoping (v1, draft)

Drafted 2026-06-19 · Shirley + Claude (Opus 4.8). Sibling to [`SCOPING.md`](./SCOPING.md) (agent-team archetype, frozen v8.2). **Not frozen.**

Adds a **second forge archetype — `workflow`** — for coding-heavy, sequential/fan-out, gate-driven work that the team archetype over-served. The forge picks between them at Phase 1.

## Why

Post-mortem of the HERC cleanup (`combiner-infra`, PR #1509) + `ticket-drainer` in `wjsl_trader`: what moved the work was a **task/gate ledger** (`TASKS.yaml`, gate sets scaled to blast radius) + a **design→implement→gate loop** + **stateless per-task/per-item subagent dispatch** + an **on-demand verification fan-out**. The persistent 5-role roster, mailbox, and rehydrate/respawn were **ceremony** — a sequential gated refactor has no live peer context to coordinate. The work wanted Workflow (which SCOPING #3 dropped) and merely tolerated agent-teams.

## Thesis — team-forge produces three composable products

Three reusable layers that **compose** (a style dispatches profiles that load skills), each independently reusable:

| Product | Is | Lives in |
|---|---|---|
| **Skills** *(foundational)* | capability/harness — `combiner-parity-check`, gate tools, domain procedures. Model/human-agnostic, composable. | `.claude/skills/` |
| **Subagents** | dispatch *profiles* that carry skills — worker/advisor/reviewer/skeptic, as **shared defaults** (not standing rosters). | `.claude/agents/` |
| **Workflow styles** | orchestration patterns — lead-loop + gate ledger + the shapes below. | `<team>-workflow/SKILL.md` + `TASKS.yaml` |

> **Terminology:** "styles" here means **orchestration patterns** (a team-forge concept). It is
> unrelated to Claude Code **output styles** (`~/.claude/output-styles/`, which shift the
> session's tone/format) — the two systems just share a word.

The product *is* the output layout. **Forging = compose:** pick a style → staff with profiles → equip with skills (discover/reuse + **produce the gaps** via `skill-creator`). Phase 3's existing `skill_gaps` block already does this — promote it to the forge's *primary* deliverable (combiner-infra created `combiner-parity-check` up front precisely because no skill did pre/post-refactor parity).

## The archetype

`workflow` = a **lead-driven task/gate loop** + bounded fan-out via Claude Code's **Workflow tool**. The lead does design→implement→gate **inline** (one followable diff); it dispatches a subagent **only** at fan-out / context-isolation / independent-verification points. No standing teammates; `status.json` is a thin index; resume = re-read `TASKS.yaml` + `status.json` (no rehydrate). The loop also has a **re-plan step**: when a gate result or implementation discovery invalidates the design, the lead re-cuts the remaining tasks before continuing (W7).

**Pick `workflow` vs `team`** by one question: *do the parallel agents hold distinct persistent peer-context they defend across rounds?* No → `workflow` (even when heavily parallel). Yes (research debate) → `team`. Stateless fan-out over independent items is a pipeline, not a team.

### Two sub-shapes (+ a modifier)

| | Sequential-gated | Parallel-drain |
|---|---|---|
| Example | `combiner-infra` | `ticket-drainer` |
| Loop | one task at a time, gated | triage → fan-out ≤N/wave → per-item gate |
| Primitive | lead loop + bursts | `pipeline(items, drain, verify)` |
| Attended | yes (review once at end) | **no — recurring/unattended** |

**`recurring + unattended` modifier** (from ticket-drainer): `/schedule` cron is the outer loop; a per-cycle box bounds each run; `status.json` is the cross-invocation handoff (carry-over resumes next cycle); `unattended: true` ⇒ per-item verify gates mandatory. Rotate the ledger per cycle (ticket-drainer's hit 176 KB / 65 tickets / 312 events).

## Frozen-candidate decisions

- **W1 — Two archetypes, one forge.** `design.yaml` gains `archetype: team|workflow`, chosen at Phase 1 triage; Phases 1–3 shared, Phase 4 branches. `workflow` is the default for refactor / migration / ticket-drain / bug-batch.
- **W2 — Runtime is a lead-driven loop.** Workflow tool reinstated for fan-out; agent-teams is **not** the runtime substrate.
- **W3 — Ledger is lead-written.** `TASKS.yaml` + `status.json`, single-writer = lead; dashboard is a render step (`gen_dashboard.py`). No tracker/monitor/verify teammates.
- **W4 — Default dispatch is the lead, inline.** The subagent is a **shared-default profile**, dispatched only at fan-out points.
- **W5 — Gates are codebase-derived, scaled to `blast_radius`.** The *machinery* is general (named gates, blast-radius scaling, advance-only-on-green); the *vocabulary* is **discovered per project from the detailed codebase** — its test suites, CI, build targets, invariants — never a fixed list team-forge ships. A gate needs a backing capability; where none exists (e.g. no pre/post-refactor parity harness), the forge **produces the skill** that backs it → gate discovery *is* skill-gap discovery for verification.
- **W6 — Resume is trivial.** Read the ledger; no rehydrate / `respawn_order`.
- **W7 — Design is a living artifact; re-plan is first-class.** Refactor design is a hypothesis the code keeps correcting (herc-cleanup rejected `SharedCombinerBase`, split numeric bugs out of parity-gated commits, re-cut into two layers). `TASKS.yaml` + the plan doc are **versioned**, not frozen Phase-3 output: the lead can re-plan mid-loop — new plan version + one-line *why* (the `team_plan_history` pattern, inherited), re-cut only the not-yet-done tasks + gates, preserve gated work, review before executing.
- **W8 — Subagent memory is Claude Code native, not hand-rolled.** A dispatched worker/advisor is stateless per call, but persistence is a platform feature — use it. Forge emits `memory: project` frontmatter on the worker + advisor profiles → Claude Code gives each a private `.claude/agent-memory/<name>/` directory, auto-injects its `MEMORY.md`, and enables Read/Write/Edit so the agent **self-curates** codebase patterns, gotchas, and ruled-out approaches across dispatches. This is why a recurring drain stops re-deriving each wave: the worker carries its own memory forward. The lead hands each dispatch a **scoped brief** (task + exact artifacts) but does NOT harvest anything back — there is no team-level memory store. Scope overridable per roster entry (`user|project|local`). *Accepted limitation:* native memory is per-agent-siloed (name-derived dir, not poolable), so there's no cross-agent shared dead-end corpus; cross-agent knowledge travels via the lead's KB + briefs. Verified against code.claude.com/docs/en/sub-agents#enable-persistent-memory (`FORGE_VERSION` 0.7.0).

- **W9 — Self-modifying tasks need a fresh session, not a worker (`dispatch: fresh_session`).** A task that edits the files the *running* session loads and depends on — `.claude/agents/**`, `.claude/skills/**`, hooks, `settings.json` — cannot be done by ANY in-session agent: inline, a `worker`, or any `Agent`-tool subagent all inherit this session's loaded config + permissions, so the edit races the very files in play (hook conflicts + partial state; cf. the combiner CLAUDE.md agent-edit rule). These are a distinct third dispatch value: the lead does NOT dispatch — it **prepares the scoped brief + branch, marks the task `blocked_on: fresh_session_handoff`, keeps draining any still-eligible tasks, and hands off** to a freshly-launched full-permission Claude session (split window). A legitimate autonomy pause only when nothing else is eligible. Root cause it fixes: `worker` and "fresh full-permission session" are *different mechanisms* — the combiner design conflated them, labeling agent-file authoring `dispatch: worker` (unsatisfiable, since a worker is an in-session subagent). `worker`/`advisor` profiles now also carry a self-guard: refuse an agent/skill/hook/settings brief and bounce it back to the lead. Validated in `forge.py` (`dispatch ∈ inline|worker|fresh_session`); `FORGE_VERSION` 0.8.0.

## Contract — `design.yaml` with `archetype: workflow`

Replaces the team `roster` / `rehydrate` / `tracking` blocks with:

```yaml
archetype: workflow
shape: sequential-gated | parallel-drain
recurring: {schedule, cycle_box, unattended, carry_over_state: status.json}   # omit if one-shot
tasks:  [{id, output, depends_on, blast_radius, gate_set, dispatch: inline|worker|fresh_session}]  # sequential-gated
queue:  {eligibility, triage, wave_size, routes}                                     # parallel-drain (instead of tasks)
gates:  {<name>: <command/criterion>}        # vocabulary DISCOVERED from the codebase (test/CI/invariants), not shipped; gaps → produced skills
worker: {model: sonnet, isolation: worktree, procedure: design→TDD→gate, skills, escalation: advisor}  # shared default
fan_out:[{when, shape, n, synthesize_to}]    # optional Workflow bursts
ledger: {state_shape: [current_plan, plan_history, ...], events: [...,replanned], dashboard_panels,
         dashboard_owner: render_step|monitor_agent,   # default render_step (lead runs gen_dashboard.py). monitor_agent -> forge emits a
         monitor: {name: monitor, model: inherit}}      #   standing monitor teammate that PULLS git/task state + flags drift (see skills/monitor). optional.
# lead-written, thin. current_plan/plan_history are RUNTIME fields (forge seeds null/[]), not contract literals (W7)
```

## Output layout (committed)

```
.claude/
  skills/<team>-<domain-skill>/SKILL.md   ★ THE PRODUCT — gap-fill skills (e.g. combiner-parity-check)
  skills/<team>-workflow/SKILL.md         entry point /<team>-workflow (the lead loop)
  agents/<team>-worker.md, -advisor.md    thin overlays → shared default + project skills (dormant)
  team-forge/<team>/{design.yaml, TASKS.yaml, tracker/status.json (thin),
                     gates/<descriptive-name>.{py,sh},          ← lead-owned gate harness (tracked)
                     playground/{dashboard.html, gen_dashboard.py},  ← ephemeral (gitignored)
                     .gitignore}                                 ← ignores playground/ + tracker/status.json
docs/team-forge/<team>/{brainstorms, team-plans, artifacts/<task-slug>, README.md}
agents/<team>-worker.md, -advisor.md → memory: project → .claude/agent-memory/<name>/  ← native per-agent memory (self-curated)
```

**Lead gate-harness home (retro #1687, item 10).** Producer≠verifier parity scripts and other
lead-authored gate checks are load-bearing evidence, not throwaway — they get a standard home at
`.claude/team-forge/<team>/gates/` with content-descriptive names (`parity-check.py`,
`post-deletion-parity.py`), referenced by the `gates:` commands in `TASKS.yaml`. They are TRACKED
(not under the ephemeral `playground/`). Teardown classifies each: reusable-beyond-this-team → move
to the project's standard tools location; single-use → remove with the rest of the scaffolding.

`<task-slug>` is the task's descriptive `id` (e.g. `post-process-runner/`), never an opaque phase
code (`t5/`). Task IDs stay in the ledger (`TASKS.yaml` + `status.json`); commits, PR titles, code
comments, and artifact filenames use the task's human-readable name. See "Naming discipline" in
SCOPING.md — the same rule governs both archetypes.

No `-tracker/-monitor/-verifier.md`; no `respawn_order`.

## Reopens from SCOPING.md

#3 (Workflow as runtime) — **reversed**. #5 (tracker+monitor teammates), the 5-role rule, and rehydrate/`respawn_order` — **dropped**. Kept: Phase 1–3 design discipline, `status.json` as resumable truth, dashboard, `docs/` KB, single-writer, design-before-code, asset discovery.

## Open decisions

1. Naming (`/<team>-workflow`; `archetype` field values).
2. One `design.yaml` with an `archetype` field vs two schemas — lean: one.
3. `TASKS.yaml` separate vs a `tasks:` block — lean: `design.yaml` = initial, `TASKS.yaml` = live runtime copy.
4. Fan-out: declare in contract vs leave to lead's judgment — lean: declare known, allow ad-hoc.
5. Team archetype stays; the *default* flips to triage-decides (most wjsl_trader work → `workflow`).
6. Re-forge the two existing teams under the new archetype? Lean: re-forge `ticket-drainer` as the parallel-drain reference (exercises cron + `pipeline()` + rotation).
7. ~~Default profiles: extension-shipped vs repo-owned `shared_across_teams`?~~ **Settled (0.9.0):** repo-owned, per team. `shared_across_teams` is retired — every forged agent is `<team>-<name>.md`, so a workflow's `<team>-worker`/`<team>-advisor` are that team's own copies and retire with it. The "promote a shared instance" half is gone: an unprefixed agent was invisible to teardown and outlived the team. The extension still ships the generic procedure (`templates/workflow/profile.md.j2`); each team forges its own instance from it.
8. Forge produces skills inline (via `skill-creator`) vs just specs the gap? Lean: scaffold + human-review before load-bearing.

## Status

**v1 — implemented.** W1–W7 are realized end-to-end, parallel to (not replacing) the agent-team path:

- **`forge.py`** — `archetype: workflow` fork: `validate_workflow` (shape, acyclic task DAG,
  `gate_set ⊆ gates`, queue for parallel-drain) + `forge_workflow` (profiles, launcher, TASKS.yaml,
  thin seeded `status.json`, `gen_dashboard.py` + dashboard). Auto-detected; team path untouched.
- **Templates** — `workflow-launcher.md.j2` (sequential-gated), `workflow-drain-launcher.md.j2`
  (parallel-drain + recurring), `workflow/profile.md.j2` (shared worker/advisor default),
  `gen_dashboard.py.j2` (render step, 6 panels incl. queue/ticket).
- **Skill branches** — Phase 1 (brainstorming triage), Phase 2 (writing-plans task list),
  Phase 3 (design: gate-vocabulary discovery + skill-gap production), Phase 4 (forge auto-detect).
- **Fixtures** — `tests/fixtures/workflow-{tidy,drain}/`, both forge clean (10 files each;
  zero stray `{{}}`; ledger seeded; dashboard renders empty + populated state).

Remaining (not blocking): freeze the W-decisions; propagate the three-product thesis up into
`SCOPING.md`; per-phase `references/review.md` workflow criteria; idempotent regen; CI.
