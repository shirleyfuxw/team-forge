---
name: team-forge:forge
description: |
  Use when emitting agent files + launcher skill + observability scaffold from a
  completed design.yaml. This is Phase 4 of the team-forge loop. Invoke after
  Phase 3 produces design.yaml and the human approves.
---

# team-forge:forge — Phase 4 (emission)

This skill emits a fully-configured agent team from a completed `design.yaml`.
Phase 3 produces the design; this skill (Phase 4) writes the actual files.

Templates are **logic-free `{{VAR}}` substitution** + named **placeholder blocks**
this skill body fills. No external Jinja2 renderer required.

## When to use

Invoke after:
- Phase 3 has produced `.claude/team-forge/<team>/design.yaml`
- The human has reviewed + approved the design
- No agent files for this team exist yet (idempotent regeneration is post-MVP)

## Inputs

- `design.yaml` at `<target_repo>/.claude/team-forge/<team>/design.yaml`
- Templates at `<team-forge-extension>/templates/`
  - `agent.md.j2` — single template with role-specific BLOCK placeholders
  - `team-launcher.md.j2` — single template
  - `dashboard.html.j2` — single template with PANELS_HTML / EVENTS_HTML placeholders
  - `design.yaml.j2` — schema reference (not used as substitution source)

## Procedure

### Step 0 — Detect hook-protected target repos

Run `git -C <target_repo> branch --show-current` and check whether the current
branch is one the project's hook setup protects (commonly `main`, `master`,
`production`). Also check if a `.claude/hooks/branch-safety.py` exists in the
target repo.

If the target repo is on a protected branch:

> "STOP. Target repo `<target_repo>` is on `<branch>`, which is hook-protected
> for direct writes. Forge will fail mid-emission if it tries to write
> `.claude/agents/*.md` etc. on this branch.
>
> Please create a feature branch or worktree first:
>
>   git -C <target_repo> checkout -b feature/<team>-forge
>
> Then re-invoke the forge skill."

Do NOT proceed.

### Step 1 — Validate design.yaml

Read `.claude/team-forge/<team>/design.yaml` and verify:

1. **Required project fields** non-empty: `name`, `target_repo`, `target_repo_basename`, `brief`
2. **Role coverage**: every role (work, verify, advise, tracker, monitor) covered by at least one roster entry (via `role` or `combined_roles`)
3. **Comms closure**: every `tracking.state_shape[].source` is either `"lead"` or a name in `roster`
4. **Milestones**: 1–5 entries (1 is acceptable for genuinely one-shot projects), each with non-empty `output` and `go_no_go`
5. **Orchestrator present**: exactly one roster entry has `role: orchestrator`

If validation fails, abort and tell the user.

### Step 2 — Compute output paths

Given `project.name` (= `<team>`) and `project.target_repo`:

- `agents_dir = <target_repo>/.claude/agents/`
- `team_skill_dir = <target_repo>/.claude/skills/<team>-team/`
- `hub_dir = <target_repo>/.claude/team-forge/<team>/`
- `kb_dir = <target_repo>/docs/superpowers/<project.target_repo_basename>/<team>/`
- `evals_dir = <target_repo>/agent_evals/<team>/`

Prefix rule:
- Non-shared roster entries → filename = `<team>-<entry.name>.md`
- Shared (`shared_across_teams: true`) → filename = `<entry.name>.md` (no prefix)

### Step 3 — Render agent .md files (per roster entry)

For each roster entry, read `templates/agent.md.j2` and perform substitution:

**Simple substitutions** (all roles):
- `{{agent_name}}` → computed filename without `.md`
- `{{purpose}}` → roster entry's `purpose`
- `{{model}}` → roster entry's `model` (default: `sonnet`)
- `{{role}}` → roster entry's `role` (or primary from `combined_roles`)
- `{{team}}` → `project.name`
- `{{project_basename}}` → `project.target_repo_basename`

**Placeholder blocks** — replace with role-specific text from the banks below:

#### `{{ROLE_DESCRIPTION_BLOCK}}` — pick by role:

- **work:** "You produce primary milestone output. Receive task assignments from the lead via the shared task list at `~/.claude/tasks/<team>/`. Hand work off to verify-role teammates before propagation. Use the mailbox (`SendMessage`) to coordinate with peers."

- **verify:** "You check outputs before they propagate. Read work-role outputs, validate against the milestone's go/no-go criteria, post verdicts to the lead via `SendMessage`, and report status updates to the team's tracker."

- **advise:** "You unblock work agents on hard problems. You are called on-demand via `Agent()` dispatch. Read shared project memory + the team's KB + the rejected-hypotheses corpus (if domain has one). Return structured advice; do not modify durable files."

- **tracker:** "You aggregate project state per the team's `tracking.state_shape` spec from design.yaml. **You are the single-writer for `.claude/team-forge/<team>/tracker/status.json`.** Read verdicts from verify-role teammates and plan outputs from the lead. Append events from `tracking.events_to_log`. Tracker is load-bearing for `/resume` — your status.json is the durable state source. Spawned FIRST on rehydrate."

- **monitor:** "You read the tracker's status.json + the narrative artifacts under `docs/superpowers/<project>/<team>/`. **You are the single-writer for `.claude/team-forge/<team>/playground/dashboard.html`.** Rewrite the dashboard per `tracking.dashboard_panels`. Trigger on every meaningful state change."

- **orchestrator:** "You are the team lead. The main session adopts this role at `/<team>-team`. You manage the shared task list, dispatch teammates, arbitrate verifier verdicts, write the team's narrative artifacts (brainstorm, plans, conclusions), and make milestone go/no-go decisions with the user. **You are the single-writer for `docs/superpowers/<project>/<team>/` narrative state.**"

(Substitute `<team>` and `<project>` placeholders within the chosen block with the actual values.)

#### `{{SKILLS_LIST_BLOCK}}`:

If `skills:` is empty: emit "*None — you work from prompt context alone. Intentional for pure prompt-driven agents.*"

Otherwise format as bulleted list: each skill name as a backticked entry on its own bullet:
```
- `<skill-name-1>`
- `<skill-name-2>`
- ...
```

#### `{{MEMORY_AUTHORITY_BLOCK}}` — pick by role:

- **tracker:** "You write only to `.claude/team-forge/<team>/tracker/status.json`."
- **monitor:** "You write only to `.claude/team-forge/<team>/playground/dashboard.html` and `dashboard-data.json`."
- **orchestrator:** "You write to `docs/superpowers/<project>/<team>/{brainstorms,team-plans,artifacts,runtime}/`."
- **work / verify / advise:** "You write to ephemeral worktrees only. No durable writes."

#### `{{SHARED_AGENT_NOTE_BLOCK}}`:

If `shared_across_teams: true`:
> "## Shared-agent note
>
> You are `shared_across_teams: true`. Forged into the target project's `.claude/agents/` once and reused unmodified by sibling teams. Do not assume team-specific context — behavior must hold across every team that spawns you."

Otherwise: empty string (no block at all).

Write each rendered agent.md to `agents_dir/<filename>`. If file exists AND `shared_across_teams: true`: skip (honor first-forged). If exists otherwise: fail with a clear error.

### Step 4 — Render team-launcher SKILL.md

Read `templates/team-launcher.md.j2`. Substitute:

- `{{team}}`, `{{project_display_name}}`, `{{target_repo}}`, `{{domain}}`, `{{project_name}}`, `{{project_basename}}` from `project` block
- `{{orchestrator_name}}` from the roster entry with `role: orchestrator` (e.g. if entry name is `lead-x` and team prefix applies, this becomes `<team>-lead-x` per the prefix rule)
- `{{CONSTRAINTS_BULLET_LIST}}` ← format `constraints[]` as bulleted list:
  ```
  - <constraint-1>
  - <constraint-2>
  ```

Write to `team_skill_dir/SKILL.md`.

### Step 5 — Initialize tracker `status.json`

Compute initial values from `design.yaml.tracking.state_shape`:
- `string` type → `null`
- `int`, `float` → `0`
- `bool` → `false`
- `list` → `[]`
- `object` → `{}`

Add universal fields:
- `current_brainstorm`: `null`
- `current_team_plan`: `null`
- `brainstorm_history`: `[]`
- `team_plan_history`: `[]`
- `events`: `[]`
- `forge_metadata`: `{forged_at_iso: <iso-now>, design_hash: <sha256-of-design.yaml>, forge_version: "0.0.1"}`

Write pretty-printed JSON (2-space indent) to `hub_dir/tracker/status.json`.

### Step 6 — Render initial dashboard

Read `templates/dashboard.html.j2`. Substitute:
- Simple: `{{team}}`, `{{project_display_name}}`, `{{project_basename}}`, `{{domain}}` from project
- `{{current_milestone}}` → `—`
- `{{current_cohort_id}}` → `—`
- `{{token_spend_cumulative_k}}` → `0`
- `{{overall_status}}` → `initial`
- `{{last_update_iso}}` → `<now>`

For `{{PANELS_HTML}}`: build HTML per panel in `tracking.dashboard_panels`:
- `milestone_timeline`: emit a `<div class="panel">` with a milestone-row per milestone (status `pending`)
- `team_roster_and_status`: emit a `<div class="panel">` with a roster-table row per teammate (status `idle`)
- `current_pointers`: emit a `<div class="panel">` showing current brainstorm/team-plan (placeholder `—`)
- Other panels: emit a `<div class="panel">` with empty-state message

For `{{EVENTS_HTML}}`: emit `<div class="empty-state">No events yet. The team is just starting.</div>`

Write rendered HTML to `hub_dir/playground/dashboard.html`. Write `{}` to `hub_dir/playground/dashboard-data.json`.

### Step 7 — Scaffold KB directory

Create:
- `kb_dir/brainstorms/` (empty)
- `kb_dir/team-plans/` (empty)
- `kb_dir/artifacts/<milestone-id>/` for each milestone
- `kb_dir/runtime/<milestone-id>/` for each milestone
- `kb_dir/README.md` (see Step 8)

### Step 8 — Generate KB README.md

At `kb_dir/README.md`, write a brief overview:
- Team name + project + domain
- Milestones list with go/no-go criteria
- Roster table
- Pointer to runtime hub + dashboard
- Pointer to design.yaml

### Step 9 — Write manifest.json

At `hub_dir/manifest.json`, record:

```json
{
  "team": "<project.name>",
  "forge_version": "0.0.1",
  "design_hash": "<sha256>",
  "forged_at_iso": "<now>",
  "generated_files": [<list with {path, kind, from_roster_entry}>],
  "shared_agents_used": [<list of {name, first_forged_by, first_forged_at_iso}>]
}
```

### Step 10 — Report success

Tell the user:
- Team forged; N files generated
- Dashboard path: `<hub_dir>/playground/dashboard.html` (open with `open <path>`)
- Launcher: `/<team>-team`

## Failure modes

- **Hook-protected branch** → Step 0 aborts with branch-creation instructions
- **Validation failed** → abort, point to what's missing
- **Existing non-shared file** → abort, suggest cleanup or regen (post-MVP)
- **Template missing** → abort, suggest reinstalling team-forge
- **Permissions** → tell user; check target_repo is writable

## What this skill is NOT

- Not an idempotent regen — that's post-MVP and requires reading the prior manifest
- Not a Jinja2-aware renderer — templates are `{{VAR}}` substitution + named placeholder blocks; no loops or conditionals are interpreted from the template

## Optional: deterministic Python renderer

team-forge ships an optional Python renderer at `tools/forge.py` (relative to
the extension root). It implements this skill's procedure deterministically
against the same logic-free templates. Requires `pyyaml`.

Two equivalent paths:
- **Agent-procedural** (this skill body): follow the steps above; the agent
  performs `{{VAR}}` substitution + fills placeholder blocks from the text banks.
- **Renderer-invoked**: shell out to `python3 <team-forge-extension>/tools/forge.py`
  passing the target design.yaml path. Faster + deterministic for repeated runs.

Both paths produce byte-identical output (the templates are logic-free; the only
variation is who computes the substitutions).
