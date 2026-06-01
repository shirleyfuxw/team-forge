---
name: team-forge-forge
description: |
  Use when emitting agent files + launcher skill + observability scaffold from a
  completed design.yaml. This is Phase 4 of the team-forge loop. Invoke after
  Phase 3 (Design) produces design.yaml and the human approves.
---

# team-forge-forge — Phase 4 (emission)

This skill emits a fully-configured agent team from a completed `design.yaml`.
Phase 3 produces the design; this skill (Phase 4) writes the actual files into
the target project.

## When to use

Invoke after:
- Phase 3 has produced `.claude/team-forge/<team>/design.yaml`
- The human has reviewed + approved the design (including the skill loadouts per teammate)
- No agent files for this team exist yet (idempotent regeneration is handled separately)

## Inputs

- `design.yaml` at `<target_repo>/.claude/team-forge/<team>/design.yaml`
- Templates at `<team-forge-extension>/templates/`
  - `agent.md.j2`
  - `team-launcher.md.j2`
  - `dashboard.html.j2`

## Procedure

### Step 1 — Validate design.yaml

Read `.claude/team-forge/<team>/design.yaml` and verify:

1. **Role coverage**: every required role (work, verify, advise, tracker, monitor) has at least one roster entry covering it (via `role` field or via `combined_roles` list)
2. **Comms closure**: every `tracking.state_shape[].source` is either `"lead"` or a name that exists in `roster`
3. **Required project fields**: `project.name`, `project.target_repo`, `project.brief` are non-empty
4. **Milestones**: 2–5 entries, each with non-empty `output` and `go_no_go`

If validation fails, abort and tell the user what's missing.

### Step 2 — Compute output paths

Given `project.name`, derive:
- `agents_dir = <target_repo>/.claude/agents/`
- `team_skill_dir = <target_repo>/.claude/skills/<project.name>-team/`
- `hub_dir = <target_repo>/.claude/team-forge/<project.name>/`
- `kb_dir = <target_repo>/docs/superpowers/<basename(target_repo)>/<project.name>/`
- `evals_dir = <target_repo>/agent_evals/<project.name>/`

Prefix rule for agent filenames:
- Non-shared roster entries: `<project.name>-<entry.name>.md`
- Shared entries (`shared_across_teams: true`): `<entry.name>.md` (no prefix)

### Step 3 — Render and write agent .md files

For each roster entry:
1. Read `agent.md.j2`
2. Substitute Jinja2 variables:
   - `agent_name` = computed filename without `.md`
   - `team` = `project.name`
   - `role`, `purpose`, `skills`, `model`, `shared_across_teams` from roster entry
3. Write to `agents_dir/<agent_name>.md`
4. If the file already exists AND `shared_across_teams: true`: skip (honor first-forged)
5. If the file already exists otherwise: fail with a clear error (idempotent regen requires manifest workflow)

### Step 4 — Render and write team-launcher skill

1. Read `team-launcher.md.j2`
2. Substitute:
   - `team` = `project.name`
   - `orchestrator_name` = roster entry with `role: orchestrator` (or fail if none)
   - `project_display_name`, `target_repo`, `project_basename`, `domain`, `constraints` from project block
3. Write to `team_skill_dir/SKILL.md`

### Step 5 — Initialize tracker `status.json`

Compute initial state from `design.yaml.tracking.state_shape`. For each field:
- `string` types → `null`
- `int`, `float` types → `0`
- `bool` → `false`
- `list` → `[]`
- `object` → `{}`

Also include:
- `current_brainstorm` = `null` (will be set on first brainstorm write)
- `current_team_plan` = `null` (will be set on first team-plan write)
- `brainstorm_history` = `[]`
- `team_plan_history` = `[]`
- `events` = `[]`
- `forge_metadata` = `{forged_at_iso: <now>, design_hash: <sha256 of design.yaml>, forge_version: "0.0.1"}`

Write JSON to `hub_dir/tracker/status.json` (pretty-printed, 2-space indent).

### Step 6 — Render and write initial dashboard

1. Read `dashboard.html.j2`
2. Substitute:
   - `team`, `project_display_name`, `project_basename`, `domain` from project
   - `dashboard_panels` = `design.yaml.tracking.dashboard_panels`
   - `roster` (with `status = "idle"` each)
   - `milestones` (with `status = "pending"` each)
   - `current_milestone`, `current_cohort_id`, `current_brainstorm`, `current_team_plan` = `None`
   - `overall_status` = `"initial"`
   - `events` = `[]`
   - `last_update_iso` = `<now>`
3. Write rendered HTML to `hub_dir/playground/dashboard.html`
4. Write empty `hub_dir/playground/dashboard-data.json` = `{}`

### Step 7 — Scaffold the KB directory

Create:
- `kb_dir/brainstorms/` (empty)
- `kb_dir/team-plans/` (empty)
- `kb_dir/artifacts/` (with per-milestone subdirs from design.yaml.milestones)
- `kb_dir/runtime/` (with per-milestone subdirs)
- `kb_dir/README.md` (auto-generated; see Step 8)

### Step 8 — Generate KB README.md

Render a `kb_dir/README.md` that:
- Names the team and project
- Lists milestones with go/no-go criteria
- Shows the roster (5 role types)
- Points at the runtime hub (`.claude/team-forge/<team>/`)
- Points at the dashboard URL (local file)

### Step 9 — Write manifest.json

At `hub_dir/manifest.json`, record:

```json
{
  "team": "<project.name>",
  "forge_version": "0.0.1",
  "design_hash": "<sha256 of design.yaml>",
  "forged_at_iso": "<now>",
  "generated_files": [
    {"path": ".claude/agents/<filename>", "kind": "agent_md", "from_roster_entry": "<name>"},
    ...
    {"path": ".claude/skills/<team>-team/SKILL.md", "kind": "team_launcher_skill"},
    {"path": ".claude/team-forge/<team>/tracker/status.json", "kind": "tracker_initial_state"},
    {"path": ".claude/team-forge/<team>/playground/dashboard.html", "kind": "initial_dashboard"},
    ...
  ],
  "shared_agents_used": [
    {"name": "<shared_agent>", "first_forged_by": "<team>", "first_forged_at_iso": "<now>"}
  ]
}
```

### Step 10 — Report success

Tell the user:
- The team has been forged
- The number and names of files generated
- The path to the dashboard (they can open it: `open <path>`)
- The launcher command: `/<project.name>-team`

## Idempotent regeneration (advanced)

On subsequent runs:
- Read existing `manifest.json` if present
- If `design_hash` in manifest matches sha256 of current design.yaml → no work needed; tell user
- If hash differs → run a diff: which files would change?
  - For each changed file: prompt user before overwriting
  - For each new file: emit normally
  - For each manifest file no longer in the new design: prompt user to delete
- Update manifest with new hash + timestamp

(Idempotent regen is post-MVP; for now, run forge only on greenfield teams.)

## Failure modes

- **Validation failed** → abort, tell user what to fix in design.yaml
- **Target file already exists (non-shared)** → abort, tell user to clean or use regen
- **Template missing** → abort, suggest reinstalling team-forge
- **Permissions error** → tell user; suggest checking target_repo is writable
