---
name: team-forge:teardown
description: |
  Use when a forged team or workflow is DONE and you want to retire it cleanly.
  "Complete" is not "cleaned up": this archives the ledger, prunes worktrees,
  removes the launcher skill + its trigger, and classifies every forged file as
  durable (keep) or ephemeral (remove). Invoke after the final go/no-go, before
  the project is considered closed.
---

# team-forge:teardown — the explicit lifecycle close

A forged team leaves a working set behind: a launcher skill (+ any hook trigger), the
per-project scaffolding (`TASKS.yaml`, `status.json`, `dashboard.html`, gate-harness
scripts), git worktrees, and agent memory. Reaching "all milestones done" does NOT remove
any of it. Without an explicit teardown the repo accumulates dead skills, stale dashboards,
orphaned worktrees, and trigger hooks that fire for a team that no longer exists.

Teardown is the **fifth phase** of the lifecycle: brainstorm → plan → design → forge → **teardown**.

## When to use

- The final milestone / last task passed its go/no-go, OR the user stops the project.
- The user explicitly asks to retire / clean up / archive a team.

Do NOT run teardown while work is in flight, or on a team whose `integration_branch` still
has un-merged, un-reviewed work — finish or hand that off first.

## Principle — classify before you delete

Every forged file is exactly one of:

- **Durable** — domain knowledge worth keeping in git: the design docs, brainstorm,
  team-plans, narrative artifacts (`migration-plan.md`, verification walkthroughs,
  certification docs), the design.yaml contract. These STAY (they are the audit trail).
- **Ephemeral** — runtime scaffolding with no durable value: `tracker/status.json`,
  `playground/` (dashboard + data), the generated dashboard HTML, the launcher skill,
  the dispatch-profile agent `.md` files, the trigger hook, worktrees, agent memory.
  These are REMOVED (or archived, see Step 1).

If you are unsure which bucket a file is in, it is durable — ask the user before removing.

## Procedure

### Step 1 — Archive the ledger (capture the run, then retire it)

Before deleting runtime state, snapshot it into the durable KB so the run is reconstructable:

1. Write a one-page **run summary** to `docs/team-forge/<team>/run-summary.md`: final status,
   what shipped (link the merged PRs / commits by their human-readable subjects), gates that
   fired, and any carry-overs. Use names, not phase IDs (see Naming discipline in SCOPING.md).
2. Copy the final `tracker/status.json` to `docs/team-forge/<team>/final-ledger.json` (the
   immutable record). The live `status.json` is ephemeral and goes in Step 4.

### Step 2 — Prune git worktrees

List worktrees created for this team's worker dispatches:

```
git -C <target_repo> worktree list
```

For each worktree that belongs to this team and has **no un-merged, un-pushed** work:

```
git -C <target_repo> worktree remove <path>
git -C <target_repo> worktree prune
```

If a worktree still holds un-merged changes, STOP and surface it to the user — do not remove it.

### Step 3 — Remove the launcher skill + its trigger

The launcher is ephemeral — it exists to drive THIS team and is dead weight afterward:

- Remove `.claude/skills/<team>-team/` (team archetype) or `.claude/skills/<team>-workflow/`
  (workflow archetype).
- Remove the forged agents — **drive this off the manifest, never off a `<team>-*` glob**:

  ```
  jq -r '.generated_files[] | select(.kind | test("agent_md|workflow_profile|monitor_agent")) | .path' \
    <target_repo>/.claude/team-forge/<team>/manifest.json
  ```

  `manifest.json` is the forge's own receipt of every file it wrote, so it is the only
  authoritative list. A `<team>-*.md` glob **silently misses shared agents**: forge names a
  roster entry `<team>-<name>.md` only when `shared_across_teams` is false — a shared entry is
  emitted as bare `<name>.md` (`combiner-skeptic.md`, not `combiner-research-skeptic.md`). Those
  are exactly the agents that survive a glob-based teardown and stay registered forever.
- **Shared agents are not yours alone to delete.** For each removal candidate whose manifest
  entry came from a `shared_across_teams: true` roster entry, check whether a sibling team in the
  same repo still references it before removing:

  ```
  grep -l '"path": ".claude/agents/<agent>.md"' <target_repo>/.claude/team-forge/*/manifest.json
  ```

  Only this team's manifest → remove it. Any sibling manifest → **keep it** and say so in the
  Step 7 report ("`combiner-skeptic` retained — still used by dynamic-ic"). Deleting a live
  sibling's agent breaks that team on its next launch.
- Remove each removed agent's native memory dir, `.claude/agent-memory/<agent-name>/` (see
  Step 6) — it is keyed by the agent's forged name, so use the same names from the manifest.
- If the forge registered a **hook trigger** for the launcher (a `settings.json` hook, a cron
  entry, or a `SessionStart` line), remove that entry too — a trigger for a deleted skill is a
  latent error. Grep the target repo's `.claude/settings*.json` for `<team>` and clean it.

If `manifest.json` is missing (hand-edited hub, or a pre-0.6 forge), fall back to the glob **plus**
an explicit read of `design.yaml`'s roster for `shared_across_teams: true` names — and say in the
report that the removal was reconstructed, not receipted.

### Step 4 — Remove ephemeral runtime state

- Remove `.claude/team-forge/<team>/playground/` (dashboard.html, dashboard-data.json,
  gen_dashboard.py) — generated, derivable, not worth tracking.
- Remove the live `tracker/status.json` and `TASKS.yaml` (the durable copy is `final-ledger.json`
  from Step 1).
- Keep `.claude/team-forge/<team>/design.yaml` + `manifest.json` ONLY if you want the forge
  receipt in git; otherwise move them under the KB. Either way, do not leave a half-populated
  hub that reads as "active."

### Step 5 — Retire the lead-owned gate harness

If the lead authored gate scripts (parity checks, deletion-safety certs), decide per script:

- **Reusable beyond this team** (a general invariant check) → move it to the project's standard
  tools location and document it; do not delete value.
- **Single-use for this team** → remove it with the rest of the ephemeral scaffolding.

(See the gate-harness convention in SCOPING.md / WORKFLOW-SCOPING.md.)

### Step 6 — Native runtime dirs

**Session-derived dirs — no action needed.** The platform's own team dirs are keyed by session
(`session-<8chars>`), not by the team slug, so team-forge can't target them by name — and doesn't
need to. The team-config dir (`~/.claude/teams/…`) is removed automatically when the session ends,
and the shared task list (`~/.claude/tasks/…`) self-expires under `cleanupPeriodDays`. Do **not**
hand-delete native `~/.claude/{teams,tasks}` dirs by team slug.

**Per-agent memory — this IS used today, and it is yours to clean.** Forge emits `memory: project`
on every `advise` roster entry and on both workflow dispatch profiles (worker + advisor), which
gives each a repo-local `.claude/agent-memory/<agent-name>/` that Claude Code auto-manages. It is
ephemeral scaffolding keyed to the agent, so it goes when the agent goes:

- For each agent removed in Step 3, remove `<target_repo>/.claude/agent-memory/<agent-name>/`.
- For a **shared agent you retained** because a sibling team still references it, **keep its memory
  dir** — that memory is the sibling's accumulated context, not this team's leftovers.
- A roster entry may override the scope (`memory: user|project|local`). `user` scope lives at
  `~/.claude/agent-memory/<agent-name>/` instead — check `design.yaml` rather than assuming the
  project-local path.

If a memory dir holds notes the user would want (hard-won codebase gotchas), offer to fold them
into the Step 1 run summary before removing — when unsure, it is durable; ask.

### Step 7 — Report + one commit

Summarize what was archived vs removed, then make ONE teardown commit (message names the team
and that it was retired — not a phase ID). Show the user the surviving durable set:

```
docs/team-forge/<team>/   ← brainstorms, team-plans, artifacts, run-summary.md, final-ledger.json
```

Confirm with the user before committing if anything was ambiguous.

## Failure modes

- **Un-merged worktree / branch** → STOP; never remove un-reviewed work. Surface it.
- **Forged agent left registered** → a `<team>-*.md` glob misses `shared_across_teams: true`
  agents (emitted as bare `<name>.md`), so they stay loaded in every future session of the target
  project — the exact burden teardown exists to remove. Always enumerate from `manifest.json`
  (Step 3), then check siblings before deleting a shared one.
- **Deleting a shared agent a sibling team still uses** → breaks that team on next launch. Grep
  the other `.claude/team-forge/*/manifest.json` first; retain and report if referenced.
- **Agent memory orphaned** → `.claude/agent-memory/<agent-name>/` outlives a deleted agent and
  accumulates silently. Remove it alongside its agent (Step 6).
- **Trigger hook left behind** → a `SessionStart`/cron entry firing a deleted skill errors every
  session; always grep `settings*.json` for `<team>` in Step 3.
- **Deleting a durable artifact** → when unsure, it is durable; ask. The KB is the audit trail.
- **Tearing down mid-flight** → refuse if tasks are still `in_progress` or the integration branch
  has open work.
