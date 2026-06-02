# team-forge

Meta-extension for Claude Code that auto-generates project-specific agent teams.

**Status:** v0.1.0 — MVP feature-complete + end-to-end forge validated. See [SCOPING.md](./SCOPING.md) for full design, [tests/README.md](./tests/README.md) for what was validated.

> **New here?** Open the interactive overview — [`docs/playgrounds/team-forge-overview.html`](./docs/playgrounds/team-forge-overview.html) — for a clickable walkthrough of what team-forge builds for the team: the 4-phase forge, the 5 role types, and the files it commits into your project.

## What it does

Forges a project-specific multi-agent team — roster, team-launcher skill, observability hub — for any project domain. Each forged team:

- Spawns persistent teammates via Claude Code's `agent-teams` primitive (experimental)
- Enforces a 5-role coverage rule: **work / verify / advise / tracker / monitor**
- Includes a runtime dashboard at `.claude/team-forge/<team>/playground/dashboard.html`
- Survives `/resume` via an explicit rehydrate protocol (tracker is load-bearing)

team-forge is the wiring; the procedural toolbox (TDD, debugging, planning, brainstorming) is provided by Superpowers and the project's own skills.

## Requires

- Claude Code v2.1.32 or later
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment
- For optional deterministic forging: `python3` + `pyyaml`

## Install

```bash
# Local development
/plugin marketplace add ~/8888/team-forge
/plugin install team-forge@team-forge-dev

# Verify
/plugin list
# should show team-forge@team-forge-dev
```

## End-to-end usage example

Below is a complete walkthrough of forging a new team for a hypothetical project. You'll run through 4 phases interactively with Claude as the lead.

### Step 0 — Set up the target repo

```bash
# Your project, on a feature branch (so .claude/ writes don't hit hook protection)
cd ~/my-cli-project
git checkout -b feature/forge-team

# Make sure the experimental flag is set
echo 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.zshrc
source ~/.zshrc
```

### Step 1 — Brainstorm (Phase 1)

In a Claude Code session:

```
Use team-forge:brainstorming to start designing an agent team for this project. The project is a Python CLI that wraps the GitHub API for batch repo operations.
```

Claude will interrogate you:
- *Goal?* → "Batch update settings across 30 repos via CLI"
- *Other agents needed?* → "Maybe a rate-limit-watcher to back off when GitHub returns 429"
- *Verification?* → "Smoke test against a single test repo before fanning out"
- *Tracking?* → "Repos processed, rate-limit headroom, error count"
- *Completion criteria?* → "100% of target repos updated OR clean failure report"
- *Token budget?* → "Soft 50k per cohort"

Claude writes `docs/superpowers/my-cli-project/<team>/brainstorms/brainstorm-phase1-initial.md` and runs the **self-review checklist** (5 criteria). Surfaces any gaps. Asks you to approve.

### Step 2 — Plan (Phase 2)

```
Now use team-forge:writing-plans to draft the team plan.
```

Claude refines milestones interactively:
- *m1-discover*: Output = list of target repos + their current settings. Go/no-go = "list is non-empty and signature-verified"
- *m2-batch-update*: Output = updated repos + audit log. Go/no-go = "all repos updated OR documented failures"

Each milestone gets: hard_dependencies, interface_to_next, expected_team_size, next_phase_check, iteration shape.

Writes `team-plans/team-plan-v1.md`. **Self-review** (9 criteria including cyclic-dependency check) before asking approval.

### Step 3 — Design (Phase 3)

```
Now use team-forge:design to produce the design.yaml.
```

Claude dispatches 3 forge-design-agents in parallel (roster-correctness lens, comms+coverage lens, domain-fit lens), reconciles their outputs, and runs **asset discovery** — skills + agents across project, user-global, installed plugins, and any configured reference libraries (e.g. ECC), domain-filtered to this project — proposing reuse/adapt candidates. Produces `design.yaml` covering:

- 6-agent roster (orchestrator + work + verify + advise + tracker + monitor)
- `tracking.state_shape` (repos_processed, rate_limit_remaining, errors_count, etc.)
- `tracking.dashboard_panels` (milestone_timeline + roster + rate_limit_gauge + error_log)
- Constraints (GitHub token env var, rate-limit handling, etc.)

**Self-review** (10 criteria) before asking you to approve.

### Step 4 — Forge (Phase 4)

```
Now use team-forge:forge to emit the team files.
```

Claude validates the design, detects whether the target_repo is on a hook-protected branch (Step 0 of the forge skill — aborts cleanly if so), and emits:

```
~/my-cli-project/
  .claude/
    agents/
      <team>-orchestrator.md
      <team>-fetcher.md
      <team>-updater.md
      <team>-rate-watcher.md
      <team>-tracker.md
      <team>-monitor.md
    skills/<team>-team/SKILL.md
    team-forge/<team>/
      design.yaml
      manifest.json
      tracker/status.json
      playground/dashboard.html
      playground/dashboard-data.json
  docs/superpowers/my-cli-project/<team>/
    brainstorms/ (with the brainstorm from Step 1)
    team-plans/ (with the plan from Step 2)
    artifacts/<milestone-id>/ (empty)
    runtime/<milestone-id>/ (empty)
    README.md
```

**Self-review** (10 criteria including manifest ↔ filesystem reconciliation) before reporting success.

### Step 5 — Launch the team

```
/<team>-team
```

The main session adopts the lead role, detects this is a fresh launch (status.json has empty state), reads the brainstorm + team-plan, spawns all teammates per `rehydrate.respawn_order`, updates status.json to milestone 1, and tells you the team is ready.

Open the dashboard to watch progress:

```bash
open ~/my-cli-project/.claude/team-forge/<team>/playground/dashboard.html
```

### Step 6 — Resume in a later session

After `/clear` or `/resume`:

```
/<team>-team
```

The launcher detects `status.json` has prior state and invokes `team-forge:rehydrate`. The lead reads tracker + KB, respawns all teammates with their prior context, logs a `rehydrate` event, triggers the monitor to refresh the dashboard, and resumes work.

### Alternative: deterministic Python renderer

If you've already hand-written a `design.yaml` and just want Phase 4 emission:

```bash
python3 ~/8888/team-forge/tools/forge.py
# Reads /tmp/test-team-forge-greeter/.claude/team-forge/greeter/design.yaml by default
# Edit the DESIGN_PATH constant at the top to point at your project's design.yaml
```

Both paths (agent-procedural via the forge skill OR Python script) produce identical output — the templates are logic-free.

## What ships in this extension

- **7 skills** (`skills/<name>/SKILL.md`): brainstorming, writing-plans, design, forge (Phase 1–4) plus rehydrate, tracker, monitor (runtime). Each phase skill has an explicit **self-review checklist** before user approval.
- **4 templates** (`templates/`): design.yaml schema reference, agent.md (with role-specific placeholder blocks), team-launcher.md, dashboard.html — all logic-free `{{VAR}}` substitution
- **Optional Python renderer** (`tools/forge.py`) — deterministic alternative to the agent-procedural path
- **Slim session-start hook** + plugin manifests + tests/ documentation

## Reference libraries (prior art, not installed)

team-forge can mine external curated corpora during Phase-3 asset discovery — without
installing them. The canonical example is **ECC** (github.com/affaan-m/ECC, MIT):
~60 agents + ~250 skills.

How it works:
- `reference-libraries/ecc.yaml` pins a specific ECC commit. ECC's files are **not**
  vendored into this repo and **never** loaded as active Claude Code skills (that would
  overflow context + pollute the namespace).
- When a project's `design.yaml` lists `ecc` under `reference_libraries:`, discovery
  fetches the pinned commit on demand into `~/.cache/team-forge/ecc/<commit>/` via
  `tools/fetch_reference.py`, domain-filters it, and proposes **adapt** candidates —
  the forge writes project-owned versions citing what it borrowed.
- `.github/workflows/bump-references.yml` runs weekly and opens a PR if the upstream
  HEAD has moved past the pin. Pins advance only via merged PR — never silently.

Materialize a pin manually:

```bash
python3 tools/fetch_reference.py reference-libraries/ecc.yaml
# prints the cache path; discovery reads <path>/agents and <path>/skills
```

## Roadmap

- [x] v0.1.0: MVP feature-complete + end-to-end forge validated
- [ ] Run the forge skill via Claude (vs the Python renderer) on a real project
- [ ] Larger-team forge test (10+ agents, real domain like HERC)
- [ ] Idempotent regeneration on subsequent forge runs
- [ ] CI: `python3 tools/forge.py` against `tests/` fixtures on every push

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
