# Contract pivot — implementation plan (2026-08-01)

Executes [GOAL.md](../../GOAL.md): the product is a **verified problem contract**
(user problem + machine-checkable verification steps); rosters/launchers/loops are
opt-in machinery; the **dashboard stays** as the agent-behavior observation surface.

This plan is itself written contract-style: every PR has a `done_when` the model
can check without the user present. The meta-procedure for all prompt deletions is
**ablation**: delete on a branch → run harness + contract check + one dogfood
transcript → re-add only what an observed failure demands. Never delete on vibes,
never keep on plausibility.

Versioning: PRs 3–5 change behavior → bump `FORGE_VERSION` + `plugin.json` +
`marketplace.json` in lockstep (drift blocks plugin updates). PRs 1–2 are
docs/tests only → no bump (precedent: PR #24).

> **Execution note (2026-08-01, Shirley's call):** executed as **one PR** with one commit
> per section below, plus a leading rescue merge — the #22–#27 stack had merged into its
> own stacked branches, never into main (verified via `git merge-base --is-ancestor`);
> `origin/feat/goal-directive` held the full accumulation and is merged in first. The
> Superpowers reference is also removed repo-wide in this PR (frozen SCOPING body kept
> intact per convention; superseded via erratum banner).

---

## PR 1 — Land the goal (docs only)

**Scope**
- `GOAL.md` (already drafted, uncommitted).
- README: rewrite the opening + "What it does" around the contract; the forge
  walkthrough moves under an explicit "when the contract demands machinery" frame.
- `SCOPING.md` + `WORKFLOW-SCOPING.md`: erratum banner at top pointing to GOAL.md
  (frozen bodies get banners, never in-place edits).

**done_when**
- [ ] `GOAL.md` exists at repo root and README's first section links it.
- [ ] `grep -l "GOAL.md" SCOPING.md WORKFLOW-SCOPING.md` → both files.
- [ ] `python3 tests/check_dashboard.py` green (no behavior change).

## PR 2 — Contract-quality check (the failure detector)

The harness verifies emission; nothing verifies elicitation. Build the acceptance
check FIRST — it is what makes every later deletion safe.

**Scope**
- `tests/check_contract.py`: validates a contract artifact —
  - `statement` non-empty and names a problem, not a task list;
  - `done_when` non-empty; **every** entry carries a `check:` the model can run
    or evaluate (command, file predicate, gate reference) — prose-only entries
    fail;
  - unresolvable conditions must be listed under `open_items`, not `done_when`;
  - `lead_decides` / `user_decides` present.
- Fixtures: one passing contract, one failing (prose done_when), wired into the
  harness alongside the 3 forge fixtures.

**done_when**
- [ ] `python3 tests/check_contract.py tests/fixtures/contract-good.yaml` exits 0.
- [ ] `...contract-bad.yaml` exits non-zero and names the prose entry.
- [ ] Harness runs both automatically.

## PR 3 — The contract skill (merge Phases 1+2)

**Scope**
- New `skills/contract/SKILL.md` replacing brainstorming (224 lines) +
  writing-plans (294): problem interrogation + verification design in one pass.
  Keep: KB survey (Step 0), goal/verification/autonomy interrogation, revision
  lineage, review checklist (now: every done_when checkable). Strip from the
  default path: roster, tracking, token-budget interrogation (moves to PR 4's
  design phase), milestone/team-size machinery.
- Deliverable: standalone `contract.yaml` in the team KB (proposed — see Open
  decisions), which `design.yaml` *references* rather than embeds.
- Route step (from PR #21) flips: **direct execution is the default**; forge
  machinery is the route that must be earned.
- Retire `skills/brainstorming/` + `skills/writing-plans/` (their references/
  review.md content folds into the contract skill's checklist).
- FORGE_VERSION bump.

**done_when**
- [ ] One dogfood run on a real ask ends with a `contract.yaml` that passes
      `check_contract.py`.
- [ ] `skills/` contains `contract/` and not `brainstorming/` or
      `writing-plans/`; no dangling references
      (`grep -r "team-forge:brainstorming\|team-forge:writing-plans"` → empty
      outside CHANGELOG/history docs).
- [ ] Harness green.

## PR 4 — Machinery demotion (design/forge opt-in)

**Scope**
- `skills/design/SKILL.md`: absorbs the team-shaped interrogation stripped in
  PR 3; entry condition = the contract's route explicitly chose machinery
  (scale / cross-session / unattended). Ablate the rest against dogfood failures.
- `skills/forge/SKILL.md` + `forge.py`: consume `contract.yaml` via design.yaml
  reference; goal block sourced from the contract, not re-elicited.
- `--resync` path documented for already-forged teams (no auto-migration).

**done_when**
- [ ] Contract-only path: a run with route `direct-execution` produces NO
      design.yaml and no `.claude/team-forge/<team>/` emission.
- [ ] Machinery path: all 3 fixtures forge green with goal block traced to
      contract.
- [ ] Harness green.

## PR 5 — Template ablation + dashboard reorientation

**Scope**
- **Interpretation over generation**: one generic runtime skill reads
  contract + TASKS.yaml live; retire the three baked launcher templates
  (workflow 230 + team 133 + drain 132 lines of per-team frozen prompt — the
  staleness class dies with them). Launcher-only policy content (lead
  discipline, dispatch rules, gate-execution contract) moves into the runtime
  skill ONCE instead of being stamped per team.
- **Dashboard reorients around the contract** (kept per GOAL.md): panels =
  contract statement + per-done_when status, gate outcomes, agent
  activity/drift events. This dissolves PR #22's L3 row-schema mismatch by
  construction — rows are contract-shaped, not design-shaped per team.
- Forge-time consumer exercise (prevention-pack idea #3): render the dashboard
  with synthetic mid-run rows, abort on undefined/blank panels.

**done_when**
- [ ] Fixtures forge with no baked launcher files; runtime skill drives the
      loop (one dogfood run to a gate outcome).
- [ ] Dashboard renders per-done_when status from a synthetic ledger with zero
      blank/undefined panels (checked at forge time).
- [ ] Harness green; `grep -r "team-plan-v1\|current_milestone"` on emitted
      fixture output → empty.

---

## Open decisions (need Shirley before the PR that hits them)

1. **Contract artifact home** (PR 3): standalone `contract.yaml` referenced by
   design.yaml (proposed — it exists before/without any design), vs. staying a
   `goal:` block inside design.yaml. Proposal: standalone.
2. **Skill names** (PR 3): hard-retire `brainstorming`/`writing-plans` vs. one
   release of thin alias skills that point at `contract`. Proposal: hard-retire
   (plugin update propagates; aliases are standing prompt cost).
3. **Goal-enforcement hooks** (pending from pre-pivot): Stop-hook blocking while
   eligible work remains + SessionStart re-injection after compaction. Fits
   naturally after PR 5; still opt-in vs default-on for unattended is her call.

## Out of scope

- Migrating already-forged teams (offer `--resync`, don't auto-touch).
- tracker/monitor/rehydrate retirement — revisit after PR 5 shows what the
  runtime skill + reoriented dashboard actually still need (ablation order:
  observe first, delete second).
- The playground overview HTML refresh (still narrates the old world; fold into
  PR 1's README pass only if cheap, else its own docs PR).
