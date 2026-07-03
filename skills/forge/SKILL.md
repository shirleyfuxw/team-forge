---
name: team-forge:forge
description: |
  Use when emitting agent files + launcher skill + observability scaffold from a
  completed design.yaml. Phase 4 of the team-forge loop. Invoke after Phase 3
  produces design.yaml and the human approves.
---

# team-forge:forge — Phase 4 (emission)

Phase 4 turns a completed `design.yaml` into a forged team: agent `.md` files,
the team-launcher skill, the tracker's initial `status.json`, the initial
dashboard, the KB scaffold, and a manifest.

The emission itself is **deterministic** and lives in `tools/forge.py` (relative
to the extension root). This skill's job is the agent-facing wrapper around it:
the pre-flight safety check, the invocation, and the post-emission review. There
is no need to hand-render templates — `forge.py` does the substitution against
the logic-free `{{VAR}}` templates in `templates/`.

## When to use

- Phase 3 produced `.claude/team-forge/<team>/design.yaml`
- The human approved the design (roster + skill loadouts + tracking spec)
- No agent files for this team exist yet (idempotent regen is post-MVP)

## Step 0 — Detect hook-protected target repos (do this first)

Forge writes into `<target_repo>/.claude/` and `<target_repo>/docs/`. Many repos
hook-protect their default branch against direct writes.

Run `git -C <target_repo> branch --show-current` and check for a
`.claude/hooks/branch-safety.py` (or similar) in the target. If the repo is on a
protected branch (commonly `main`, `master`, `production`):

> "STOP. Target repo `<target_repo>` is on `<branch>`, which is hook-protected
> for direct writes. Forge will fail mid-emission. Create a feature branch or
> worktree first:
>
>   git -C <target_repo> checkout -b feature/<team>-forge
>
> Then re-invoke forge."

Do NOT proceed until the target is on a writable branch.

## Step 0b — Target-repo tooling & robustness preflight

The forged team will operate inside the target repo's hook environment. Three known incompatibilities
cost real rework in the alpha-variant-system run (retro #1687, items 6–8). Detect them now and warn
the user — team-forge can't rewrite the target's hooks, but a forged team that walks into them blind
ships churn and bypasses gates. Grep `<target_repo>/.claude/settings*.json` + `.claude/hooks/`:

1. **Auto-formatter PostToolUse hook (item 6).** A formatter that runs on every `Edit` and re-churns
   unrelated lines (quote style, line collapsing) fights the surgical-edit rule — it turns a 3-line
   change into an 80-line diff and can ship churn into production-critical files. If one exists, tell
   the user to **scope the formatter to changed lines, pre-align the repo to the formatter style, or
   bless a binary-write path** for the worker before running the team. Note it in the team's
   `constraints`.

2. **Review-receipt PostToolUse hook under worktrees (item 7).** A "mandatory review receipt" hook
   that inspects staged files runs in the **harness CWD (main repo)**, not the Bash tool's worktree
   CWD — so under the worktree workflow team-forge prescribes it never detects the worktree's staged
   files and gets blanket-bypassed (`SKIP_REVIEW_CHECK=1` on every commit), silently defeating the
   gate. If one exists, tell the user to **make the hook worktree-aware** (resolve the worktree CWD)
   or **define a worktree-native receipt flow** before relying on it.

3. **Model fallback on provider outage (item 8).** When a provider tier is globally unavailable
   mid-run, dispatched agents on that tier FAIL the stage. The launcher templates instruct the lead
   to **fall back one tier** (e.g. fable → opus) on a provider-unavailable error rather than failing —
   confirm the design's `model` choices have a sane fallback and that critical stages aren't pinned to
   a single tier.

These are warnings, not hard aborts — proceed if the user accepts the risk, but record the decision.

## Step 1 — Run the renderer

```
python3 <team-forge-extension>/tools/forge.py <target_repo>/.claude/team-forge/<team>/design.yaml
```

`forge.py` performs, in order:
1. **Validation** — schema parse, role coverage (work/verify/advise + exactly one orchestrator; tracker/monitor are OPTIONAL — absent means lead-written ledger + render-step dashboard), comms closure (every `tracking.state_shape[].source` resolves to a roster entry or `"lead"`), 1–5 milestones each with `output` + `go_no_go`. Aborts with a clear message on failure.
2. **Path computation** — agents_dir, team_skill_dir, hub_dir, kb_dir, evals_dir. Prefix rule: non-shared → `<team>-<name>.md`; `shared_across_teams: true` → `<name>.md`.
3. **Agent `.md` emission** — one per roster entry, role-specific description + memory-authority + suggested-skills blocks substituted from the role text banks defined in `forge.py`. Skills also land in the agent's `skills:` frontmatter — preloaded when the agent runs as a dispatched subagent; documentation-of-intent when it runs as a teammate.
3b. **Skill-gap scaffolds** — one DRAFT `SKILL.md` per `skill_gaps:` entry, emitted to
   `.claude/team-forge/<team>/skill-drafts/<name>/` (NOT directly to `.claude/skills/`).
   Each carries a promotion checklist; a human reviews, runs the acceptance check green,
   then promotes the directory to `.claude/skills/<name>/`. This is the forge's primary
   deliverable — skills outlive the team.
4. **Team-launcher skill** — `<team>-team/SKILL.md` from `team-launcher.md.j2`.
5. **Initial `tracker/status.json`** — empty state typed from `tracking.state_shape` + `forge_metadata` (forged_at_iso, design_hash, forge_version).
6. **Initial `dashboard.html`** — the self-contained interactive shell (`dashboard.html.j2`) with the initial payload (built from `tracking.dashboard_panels` + the empty `status.json`) embedded in its single `{{DASHBOARD_DATA_JSON}}` slot. Same shell the monitor (team) / `gen_dashboard.py` (workflow) rewrite at runtime.
7. **KB scaffold** — `docs/team-forge/<team>/{brainstorms,team-plans,artifacts/<id>,runtime/<id>}/` + README.
8. **manifest.json** — generated-files list + design_hash.

If Python or `pyyaml` is unavailable, the same procedure can be followed by hand
against the templates — but prefer the renderer; it is the source of truth for
the emission logic and the per-role text banks.

## Workflow archetype (`archetype: workflow`)

`forge.py` **auto-detects** `archetype: workflow` at the top of design.yaml and takes the
workflow emission path — you run the exact same command (Step 1), no flag. What differs:

- **Validation** — instead of the team role-coverage rule, it checks: a valid `shape`
  (`sequential-gated` | `parallel-drain`), a `gates` vocabulary, a `worker` profile, a
  `ledger.state_shape`, and either (sequential-gated) an **acyclic task DAG** with every
  task's `gate_set ⊆ gates` and `dispatch ∈ {inline, worker}`, or (parallel-drain) a `queue` block.
- **Emitted files** (no 5-agent roster):
  - `.claude/agents/<team>-worker.md` + `<team>-advisor.md` — the shared-default dispatch profiles.
  - `.claude/skills/<team>-workflow/SKILL.md` — the lead-loop launcher (`/<team>-workflow`):
    sequential-gated gets the task/gate loop; parallel-drain gets the triage→`pipeline()` drain loop.
  - `.claude/team-forge/<team>/TASKS.yaml` — the live runtime work list (tasks/queue + gates).
  - `skill-drafts/<name>/SKILL.md` per `skill_gaps:` entry — same DRAFT/promote flow as the
    team path (step 3b above); a gate calling an unpromoted skill fails-closed by design.
  - `tracker/status.json` — **thin** ledger seeded from `ledger.state_shape` (current_plan→null, etc.).
  - `playground/gen_dashboard.py` + the `dashboard.html` it renders — the render step, **no monitor agent**.
  - `design.yaml` copy + KB README + manifest.
- **Launcher** is `/<team>-workflow` (not `/<team>-team`); there is **no roster to spawn** —
  the lead drives the loop and dispatches the worker profile only at fan-out points.

Worked references: `tests/fixtures/workflow-tidy/` (sequential-gated) and `workflow-drain/`
(parallel-drain + recurring). Step 0 (hook check), Step 2 (review), Step 3 (report) are identical.

## Step 2 — Review the output

Run the forge output review (`references/review.md`) — either inline or via a
dispatched review subagent (see the "Output review" section below). This
reconciles the manifest against the filesystem and validates the emitted files
before you report success.

## Step 3 — Report

Tell the user:
- Team forged; N files generated
- Dashboard path: `<hub_dir>/playground/dashboard.html` (open with `open <path>`)
- Launcher: `/<team>-team`

## Failure modes

- **Hook-protected branch** → Step 0 aborts with branch-creation instructions
- **Validation failed** → `forge.py` prints what's missing; fix design.yaml
- **Existing non-shared file** → abort; clean up or wait for idempotent regen (post-MVP)
- **Template or pyyaml missing** → install `pyyaml`, or hand-render against `templates/`
- **Permissions** → check target_repo is writable on the current branch

## Output review

The review checklist for Phase 4 lives at `references/review.md` — extracted so a
separately-dispatched **review subagent** can load just the criteria without this
skill's procedure (context isolation).

Two equivalent paths:

1. **Inline** — read `references/review.md`, run the checklist against the emitted
   files + manifest, surface ✓/✗ to the user.
2. **Subagent** — dispatch with:
   > "Review the forge output. Reconcile `<target>/.claude/team-forge/<team>/manifest.json`
   > against the filesystem and validate each emitted file using the criteria in
   > `references/review.md` of the team-forge forge skill. Report ✓/✗; name gaps."

Do NOT report success if any hard-abort trigger in `references/review.md` fires.
