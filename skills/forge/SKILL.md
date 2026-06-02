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

## Step 1 — Run the renderer

```
python3 <team-forge-extension>/tools/forge.py <target_repo>/.claude/team-forge/<team>/design.yaml
```

`forge.py` performs, in order:
1. **Validation** — schema parse, role coverage (work/verify/advise/tracker/monitor + exactly one orchestrator), comms closure (every `tracking.state_shape[].source` resolves to a roster entry or `"lead"`), 1–5 milestones each with `output` + `go_no_go`. Aborts with a clear message on failure.
2. **Path computation** — agents_dir, team_skill_dir, hub_dir, kb_dir, evals_dir. Prefix rule: non-shared → `<team>-<name>.md`; `shared_across_teams: true` → `<name>.md`.
3. **Agent `.md` emission** — one per roster entry, role-specific description + memory-authority + suggested-skills blocks substituted from the role text banks defined in `forge.py`.
4. **Team-launcher skill** — `<team>-team/SKILL.md` from `team-launcher.md.j2`.
5. **Initial `tracker/status.json`** — empty state typed from `tracking.state_shape` + `forge_metadata` (forged_at_iso, design_hash, forge_version).
6. **Initial `dashboard.html`** — rendered from `dashboard.html.j2` + `tracking.dashboard_panels`, empty state.
7. **KB scaffold** — `docs/superpowers/<basename>/<team>/{brainstorms,team-plans,artifacts/<id>,runtime/<id>}/` + README.
8. **manifest.json** — generated-files list + design_hash.

If Python or `pyyaml` is unavailable, the same procedure can be followed by hand
against the templates — but prefer the renderer; it is the source of truth for
the emission logic and the per-role text banks.

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
