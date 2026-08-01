# team-forge

Meta-extension for Claude Code that auto-generates project-specific agent teams.

**Status:** v0.5.0 — **skills-as-product emission** (`skill_gaps` contract → DRAFT scaffolds → human promotion), **tracker/monitor demoted to optional roles** (default: lead-written ledger + `gen_dashboard.py` render step, both archetypes), and re-alignment to the 2026-06 agent-teams platform update (implicit per-session teams, `Task*` tools, `model: inherit` default — see [docs/agent-teams-primitive-notes.md](./docs/agent-teams-primitive-notes.md)). v0.4.0 shipped the unified self-contained interactive dashboard ([docs/specs/2026-06-23-playground-dashboard-migration.md](./docs/specs/2026-06-23-playground-dashboard-migration.md)); prior v0.3.0 retro #1687 fixes folded in. See [SCOPING.md](./SCOPING.md) (agent-team) + [WORKFLOW-SCOPING.md](./WORKFLOW-SCOPING.md) (workflow) for the designs, [tests/README.md](./tests/README.md) for what was validated.

> **New here?** Open the interactive overview — [`docs/playgrounds/team-forge-overview.html`](./docs/playgrounds/team-forge-overview.html) — for a clickable walkthrough of what team-forge builds for the team: the 4-phase forge, the 5 role types, and the files it commits into your project.

## What it does

Forges a project-specific agent setup — gap-fill **skill drafts**, roster or workflow loop, launcher skill, observability hub — for any project domain:

- **Skills are the product** — Phase 3 records capabilities no existing asset covers (`skill_gaps`); Phase 4 emits a DRAFT scaffold per gap for human review + promotion to `.claude/skills/`. These outlive the team (see [Skills are the product](#skills-are-the-product)).
- **Two archetypes**, chosen by a Phase-1 work-shape triage (see [Two archetypes](#two-archetypes)):
  - `team` — persistent teammates via Claude Code's `agent-teams` primitive (experimental), role coverage **work / verify / advise** (+ the lead); survives `/resume` via an explicit rehydrate protocol. **tracker / monitor are optional** — by default the lead writes `status.json` and a forged `gen_dashboard.py` render step owns the dashboard (same machinery as the workflow archetype); add them as standing teammates only when tracking load justifies it
  - `workflow` — a lead-driven task/gate loop with no standing roster; worker profiles dispatched only at fan-out points
- Runtime dashboard at `.claude/team-forge/<team>/playground/dashboard.html`

team-forge is the wiring; the procedural toolbox (TDD, debugging, planning, brainstorming) is provided by Superpowers and the project's own skills.

## The four phases — inputs → outputs

Each phase consumes the previous phase's artifact and hands the next a stricter one:
**narrative → contract → files**. Plan decides *what work*; design decides *who does it and
how it's verified*; forge decides **nothing** (a deterministic render). If forge would have
to decide something, the design is incomplete — and if design would have nothing left to
decide, skip it (see [routes](#huge-project-forge-vs-small-build-up) below).

| Phase | Skill | Input | Output | Read by |
|---|---|---|---|---|
| **1 Brainstorm** | `team-forge:brainstorming` | your goal + the codebase + the existing team KB if any (Step-0 survey); interactive | dated `docs/team-forge/<team>/brainstorms/<slug>-brainstorm-<YYYY-MM-DD>.md` — working understanding: completion criteria, verification needs, budget, **archetype triage** (team vs workflow), milestone sketch | you + Phase 2 |
| **2 Plan** | `team-forge:writing-plans` | the current brainstorm + you (interactive); the current plan + tracker when revising | dated `team-plans/<slug>-plan-<YYYY-MM-DD>.md` — team: milestones (output, go/no-go, hard deps, interfaces, team size); workflow: **ordered task list = the proto-TASKS.yaml** (output, `depends_on`, `blast_radius`, dispatch, gate sketch). Ends with **`## Next-phase route`** | you; Phase 3 — or execution directly on the fast paths |
| **3 Design** | `team-forge:design` | brainstorm + team-plan + the repo's **verification surface** (test suites, CI, build targets) + asset discovery (project / user / plugin / reference-library skills & agents) | `.claude/team-forge/<team>/design.yaml` — the machine contract: roster or worker/advisor profiles (reuse/adapt/new), **gate vocabulary**, `skill_gaps`, ledger spec, constraints, fan-out points | you approve it; `forge.py` parses it |
| **4 Forge** | `team-forge:forge` → `tools/forge.py` | the approved design.yaml + `templates/` | emitted files in the target repo: agent profiles, launcher skill, `TASKS.yaml`, `tracker/status.json`, skill-draft scaffolds, KB scaffold, `manifest.json` (+ dashboard **only** when recurring / `ledger.dashboard: true` / monitor-owned) | the running team, and `/resume` rehydrate |

Costs are deliberately asymmetric: Phases 1–2 are cheap conversations; Phase 3 is the
expensive one (parallel design agents + reciprocal review); Phase 4 is ~free (a script).
That's why the routing decision lives at the *end of Phase 2*.

### Huge-project forge vs small build-up

The full 1→2→3→4 pipeline is priced for a **big project**: a fresh team, an unfamiliar
domain, gates that must be discovered from the repo, skills that don't exist yet,
work that spans sessions or recurs on a schedule. For anything smaller, Phase 2's
`## Next-phase route` picks a shorter exit (you approve the route either way):

| Route | When | What actually runs |
|---|---|---|
| `phase-3-design` (full) | fresh team; roster, gate vocabulary, or skill gaps still open; long-lived / recurring / cross-session work | 1 → 2 → 3 → 4 → launch |
| `fold-into-existing-runtime` | a follow-on plan **inside an already-forged slug**, reusing its roster + gate vocabulary | 1 (light) → 2 → append the plan's tasks to the existing `TASKS.yaml`, update the tracker → resume the existing loop. No design revision, nothing re-forged |
| `direct-execution` | small **same-session** goal: no new agents, no skill gaps, gates already runnable | 1 (light) → 2 → the lead works the task list directly with existing subagents/skills. **Nothing is forged** — a launcher skill only earns its keep across sessions |

Guardrails, so the fast paths stay honest: unresolved brainstorm carry-overs force
`phase-3-design` (open design questions can't be skipped past); the Phase-2 review
checklist requires the route to be stated *and earned*; and the fast path is an on-ramp,
not a lock-in — the moment the work outgrows it (a task needs a gate that doesn't exist,
a skill gap appears, work spills across sessions, a new kind of worker is needed), stop
and run Phase 3 **for the delta**: revise design.yaml, re-forge just what changed
(`forge.py --resync` handles template drift; a new profile or gate is a design delta).

The build-up direction is the intended default for evolving projects: **start small,
let the work prove it needs machinery, then forge exactly that machinery** — rather than
forging a full apparatus up front and paying to maintain scaffold the project never uses.

## Requires

- A Claude Code version with experimental agent-teams support
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment (agent teams are
  experimental and off by default — this flag is the real gate)
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

Below is a complete walkthrough of forging a new team for a hypothetical project — the **full, huge-project route**. You'll run through 4 phases interactively with Claude as the lead. (Small scopes usually exit earlier — see [Huge-project forge vs small build-up](#huge-project-forge-vs-small-build-up).)

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

Claude writes `docs/team-forge/<team>/brainstorms/brainstorm-phase1-initial.md` and runs the **self-review checklist** (5 criteria). Surfaces any gaps. Asks you to approve.

### Step 2 — Plan (Phase 2)

```
Now use team-forge:writing-plans to draft the team plan.
```

Claude refines milestones interactively:
- *m1-discover*: Output = list of target repos + their current settings. Go/no-go = "list is non-empty and signature-verified"
- *m2-batch-update*: Output = updated repos + audit log. Go/no-go = "all repos updated OR documented failures"

Each milestone gets: hard_dependencies, interface_to_next, expected_team_size, next_phase_check, iteration shape.

Writes a dated, content-descriptive plan (`team-plans/<slug>-plan-<YYYY-MM-DD>.md`, e.g. `combiner-v3-rewrite-plan-2026-07-02.md`). **Self-review** (9 criteria including cyclic-dependency check) before asking approval.

### Step 3 — Design (Phase 3) — *sometimes skippable*

Phase 3 is not unconditional. Phase 2 ends by recommending a route (recorded in the
plan's `## Next-phase route`): a follow-on plan for an **already-forged** team skips
straight to appending its tasks to the existing `TASKS.yaml`; a **small same-session
goal** with no new agents/skills/gates skips Phases 3 *and* 4 entirely — the lead
executes the plan's task list directly with existing subagents/skills (a launcher
skill only pays off across sessions). Otherwise:

```
Now use team-forge:design to produce the design.yaml.
```

Claude dispatches 3 forge-design-agents in parallel (roster-correctness lens, comms+coverage lens, domain-fit lens), reconciles their outputs, and runs **asset discovery** — skills + agents across project, user-global, installed plugins, and any configured reference libraries (e.g. ECC), domain-filtered to this project — proposing reuse/adapt candidates. Produces `design.yaml` covering:

- 6-agent roster (orchestrator + work + verify + advise + tracker + monitor — tracker/monitor
  are optional; omit them and the lead owns `status.json` + the `gen_dashboard.py` render)
- `tracking.state_shape` (repos_processed, rate_limit_remaining, errors_count, etc.)
- `tracking.dashboard_panels` (milestone_timeline + roster + rate_limit_gauge + error_log)
- `skill_gaps` — capabilities no discovered asset covers (e.g. a smoke-test harness the repo
  lacks), each with a trigger-first description, backing gate/role, and a **runnable acceptance
  check** (the quality bar lives in the design.yaml schema + the design skill)
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
      skill-drafts/<gap-name>/SKILL.md   ← DRAFT per skill_gaps entry (promote after review)
      playground/dashboard.html
      playground/dashboard-data.json
  docs/team-forge/<team>/
    brainstorms/ (with the brainstorm from Step 1)
    team-plans/ (with the plan from Step 2)
    artifacts/<milestone-id>/ (empty)
    runtime/<milestone-id>/ (empty)
    README.md
```

Emitted agent `.md` files carry their `model` and proposed `skills` in frontmatter —
**preloaded** (full content injected) when the agent runs as a dispatched subagent; agent-teams
teammates ignore the field and load all project + user skills, so for them it documents intent.

If the design declares `skill_gaps`, each gets a **DRAFT scaffold** under
`skill-drafts/<name>/SKILL.md` — never emitted straight into `.claude/skills/`. Review it
against its promotion checklist, run its acceptance check green, then move the directory to
`.claude/skills/<name>/`. A gate that calls an unpromoted skill fails-closed (intentional).

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
python3 ~/8888/team-forge/tools/forge.py <target_repo>/.claude/team-forge/<team>/design.yaml
# auto-detects archetype (team vs workflow) from the design.yaml
```

Both paths (agent-procedural via the forge skill OR Python script) produce identical output — the templates are logic-free.

## What ships in this extension

- **8 skills** (`skills/<name>/SKILL.md`): brainstorming, writing-plans, design, forge (Phase 1–4) plus rehydrate, tracker, monitor (runtime) and teardown (the lifecycle close — archive, prune, retire). Each phase skill has an explicit **self-review checklist** before user approval.
- **9 templates** (`templates/`): design.yaml schema reference, agent.md, team-launcher.md, dashboard.html + gen_dashboard.py, the two workflow launchers (sequential-gated + parallel-drain), workflow/profile.md, and skill-gap.md (the DRAFT scaffold with its promotion checklist) — all logic-free `{{VAR}}` substitution
- **Optional Python renderer** (`tools/forge.py`) — deterministic alternative to the agent-procedural path
- **Slim session-start hook** + plugin manifests + tests/ documentation

## Skills are the product

The highest-value forge output is not the agents — it's the **gap-fill skills** that outlive
the team ([WORKFLOW-SCOPING.md](./WORKFLOW-SCOPING.md)). The pipeline:

1. **Discover** (Phase 3) — skills + agents across project / user-global / plugins / reference
   libraries, domain-filtered; bucketed into reuse / adapt / collision / pattern-reference.
2. **Identify gaps** — a needed capability nothing covers; most often a **gate with no backing
   harness** (`kind: verification` — gate discovery *is* skill-gap discovery). Recorded as
   `skill_gaps:` entries in design.yaml, each held to a quality bar: **one capability** (not a
   task note), **trigger-first description** ("Use when …"), **runnable acceptance check**,
   purpose anchored in the project's domain + verification posture, discovery-first (prior art
   cited when adapting).
3. **Forge drafts** (Phase 4) — one DRAFT scaffold per gap at
   `.claude/team-forge/<team>/skill-drafts/<name>/SKILL.md`.
4. **Promote** (human) — review against the scaffold's promotion checklist, run the acceptance
   check green, move to `.claude/skills/<name>/`. Until promoted, gates that call the skill
   fail-closed.

Worked example: `tests/fixtures/workflow-tidy/` declares `tidy-parity-check` backing its
`parity` gate — the forge emits its draft alongside the 10 base files.

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

## Two archetypes

team-forge forges one of two archetypes, chosen by a Phase-1 work-shape triage:

- **`team`** (original) — a persistent multi-agent roster for parallel, open-ended,
  multi-perspective work (research cohorts, debate). See [SCOPING.md](./SCOPING.md).
- **`workflow`** — a lead-driven task/gate loop for coding-heavy, sequential or fan-out,
  gate-driven work (refactor, migration, ticket-drain). No standing roster; the lead drives
  the loop and dispatches a shared-default worker only at fan-out points. Two shapes —
  **sequential-gated** + **parallel-drain** (with a recurring/unattended modifier). See
  [WORKFLOW-SCOPING.md](./WORKFLOW-SCOPING.md). `forge.py` auto-detects `archetype: workflow`.

## Roadmap

- [x] v0.1.0: MVP feature-complete + end-to-end forge validated (team archetype)
- [x] `workflow` archetype — both shapes (sequential-gated + parallel-drain + recurring)
  implemented in `forge.py` + templates + the Phase-1–4 skill branches; validated end-to-end
  on `tests/fixtures/workflow-{tidy,drain}/`
- [x] Skills-as-product emission — `skill_gaps` contract block + DRAFT scaffolds with a
  promotion checklist; proposed loadouts in `skills:` frontmatter (preloaded at subagent dispatch)
- [x] Re-aligned to the 2026-06 agent-teams platform update — implicit per-session teams,
  `Task*`-tool task-list access, `model: inherit` default, enforced `tools`/`model` frontmatter
  ([docs/agent-teams-primitive-notes.md](./docs/agent-teams-primitive-notes.md))
- [ ] Run the forge skill via Claude (vs the Python renderer) on a real project
- [ ] Larger forge test (real domain like HERC)
- [ ] Idempotent regeneration on subsequent forge runs
- [ ] CI: `python3 tools/forge.py` against `tests/` fixtures on every push

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
