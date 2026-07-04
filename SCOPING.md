> ⚠️ **ERRATA (2026-07-02).** This frozen v8.3 doc predates a Claude Code agent-teams update.
> Its runtime specifics are **superseded** by `docs/agent-teams-primitive-notes.md` (see the
> re-verification banner there). Notably: the native task/team dirs are now **session-derived**
> (`session-<8chars>`), not team-slug-keyed — see lines ~139 and ~245-247; the version pin at
> line 17 is stale (agent teams are experimental, gated only by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`);
> and the native hook events (line ~337) still fire, but their `team_name` payload is now
> session-derived and deprecated. The frozen body below is kept intact as the historical record.
> The two load-bearing bets — rehydrate-on-`/resume` and the single-writer file-state model —
> **remain valid**.
>
> **Decision #5 revised (2026-07-02):** tracker + monitor are now **OPTIONAL** roster roles,
> not required. The default converges on the workflow archetype's state machinery — the lead
> writes `tracker/status.json` (single-writer) and a forged `gen_dashboard.py` render step
> owns the dashboard. Add standing tracker/monitor teammates only when tracking load justifies
> them. Rationale: post-workflow-archetype review found the two roles were ~40% of a roster
> re-doing what lead file-writes + a deterministic render produce for ~zero tokens.
>
> **KB doc filenames now dated + content-descriptive (2026-07-02):** the frozen body specifies a
> generic `team-plan-v<n>.md` (KB layout ~line 231; naming-discipline carve-out ~line 279).
> Superseded — the rule now applies to **every accumulating narrative doc** in a team's KB
> (`docs/team-forge/<team>/…`): the filename must be a meaningful, content-descriptive slug that
> carries a time marker, never a generic/undated name. A team accumulates *several* of these over
> its life, so each must be self-distinguishing.
> - **Team-plans:** `<slug>-plan-<YYYY-MM-DD>.md` (e.g. `combiner-v3-rewrite-plan-2026-07-02.md`),
>   never `team-plan-v1`. Same-day revision → append `-v2`. A **post-completion improvement round
>   is a *new* dated plan** whose slug names its focus (`…-improvements-2026-08-15.md`), not a
>   version bump on the finished plan.
> - **Brainstorms:** already dated (`brainstorm-<YYYY-MM-DD>.md`) — unchanged.
> - **Design / exploration narratives & other artifacts** (design walkthroughs, verification
>   walkthroughs, section conclusions, decision records): content-descriptive slug + a date (or,
>   for per-iteration docs, the iter-id). Dating them keeps multiple docs distinguishable/orderable.
> - **Exception — fixed-name machine contracts stay fixed:** exactly-one, machine-read files are
>   NOT dated or renamed: `design.yaml`, `status.json`, `TASKS.yaml`, `manifest.json`,
>   `dashboard.html`/`dashboard-data.json`, and the KB `README.md`. Consumers (forge.py, tracker,
>   monitor, launchers) resolve these by fixed name; the tracker's current-pointers + history arrays
>   carry ordering, so narrative filenames need no global version counter.
>
> This retires the "acceptable exception" carve-out for `team-plan-v1.md` and generalizes
> naming-discipline rule #3. The team/workflow launchers no longer assume a fixed bootstrap plan
> filename — they read the one plan file present (or the tracker/`design.yaml` pointer).
>
> **Subagent memory = Claude Code native (2026-07-03):** the frozen "Memory model — file-based
> coordination" section (~line 353) left the *subagent's* memory thin — spawn handed pointers +
> "derive your own read paths," nothing persisted across dispatches, and the advise role's
> "rejected-hypotheses corpus" was a dangling pointer (never created). Resolved by adopting Claude
> Code's **native per-agent memory** rather than a hand-rolled store (an initial file-based store was
> built, then dropped in favor of the platform feature — verified against
> code.claude.com/docs/en/sub-agents#enable-persistent-memory):
> - **Dispatched roles get native memory.** Forge emits `memory: project` frontmatter on dispatched
>   subagents (advise; workflow worker/advisor). Claude Code gives each a private
>   `.claude/agent-memory/<name>/` directory, auto-injects its `MEMORY.md`, and enables Read/Write/Edit
>   so the agent **self-curates** patterns, gotchas, and ruled-out approaches across dispatches. No lead
>   harvesting, no team-level store. Scope overridable per roster entry (`user|project|local`).
> - **Teammates get none — by platform design.** On the agent-teams teammate path Claude Code applies
>   only `tools` + `model` (+ appends the definition body); `memory`, `skills`, `mcpServers` are
>   ignored. So standing work/verify teammates have no per-agent memory: their durable context is this
>   KB + the shared task list, and the lead hands each a scoped brief on (re)spawn.
> - **Accepted limitation.** Native memory is per-agent-siloed (the directory is name-derived, not
>   poolable), so there is no cross-agent shared dead-end corpus — an advisor cannot read a worker's
>   ruled-out approaches. Cross-agent knowledge travels through the lead's KB + briefs instead.
> Wired into `agent.md.j2`, `workflow/profile.md.j2`, all three launchers, and `forge.py`
> (`memory_frontmatter_block`, `DISPATCHED_MEMORY_ROLES`); `FORGE_VERSION` 0.7.0.

# team-forge — scoping (v8.3, frozen + docs/team-forge KB root)

Drafted 2026-05-31 by Shirley + Claude (Opus 4.7).
Status: **design phase, frozen for implementation. No more reshuffling.**

**This is the freeze point.** v7 went through a critical opus review (preserved on the `design-history` branch) that surfaced 10 specific issues — 3 buildability blockers, 7 design-decisions-needed. All 6 of the resulting v8 decisions are locked. Items resolved in earlier versions are not re-litigated.

**The 6 frozen decisions:**

1. **Multi-session resume — agent-teams + rehydrate protocol.** team-forge bets on Claude Code's agent-teams primitive. Teammates evaporate on `/resume`. The forged lead's first action on resume is **read tracker/status.json + hub directory → respawn all teammates with their state**. Tracker is load-bearing.
2. **Phase 3 → Phase 4 contract is annotated YAML, not markdown.** Phase 3 produces one artifact: `design.yaml` (richly commented, human-reviewable, machine-parseable). v6's "design as markdown doc" framework is dropped. (Worked example file `phase3-design.herc.md` is now historical.)
3. **Drop Workflow as a runtime primitive entirely.** agent-teams native fan-out (multiple teammates assigned similar tasks via the shared task list) is sufficient. No teammate-internal Workflow. No forge-emitted .js for runtime. Workflow remains useful as a META tool for building team-forge itself.
4. **Extension scope = generic forging machinery + generic shared skills + templates only.** Domain-specific agents and skills (combiner-skeptic, combiner-librarian, combiner-team launcher, combiner-peer-debate) belong to the TARGET PROJECT, not the extension. "Shared across teams" means *shared across forged teams within the same project's `.claude/`* — `combiner-skeptic` is forged into `wjsl_trader/.claude/agents/` once by HERC and reused by sibling combiner-research teams. The extension stays generic. *(v8.1 correction — v8's "bundle everything" framing conflated extension-level sharing with project-level sharing.)*
5. **Tracker + monitor stay as separate teammates.** 5 roles total. Tracker is load-bearing (rehydrate source of truth). Monitor reads tracker + writes dashboard.
6. **Drop Phase 2.5 reviewer.** Phase 3 spawns multiple forge-design-agents in parallel; their reciprocal review IS the coverage gate. Workflow simplifies to 4 phases.

> **⚠ Requires:** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Claude Code v2.1.32+. Agent teams remain experimental.

---

## What team-forge is

> Interactive overview: [`docs/playgrounds/team-forge-overview.html`](./docs/playgrounds/team-forge-overview.html) — a clickable explorer of the 4-phase forge, the 5 role types, and the forged output layout described below.

A meta-extension that **auto-generates project-specific agent teams** for Claude Code's agent-teams primitive. Feed it a project context. It runs a human-in-the-loop 4-phase design loop ending with concrete files committed to the target project: agent definitions, a team-launcher skill, and the team's durable hub directory.

team-forge is also a **generic shared resources hub** — it bundles only the *generic* pieces reusable across every project domain:
- Shared skills (agent-team-aware brainstorming, planning, design, forge, tracker, monitor, rehydrate patterns)
- Templates (design.yaml skeleton, agent.md.j2, team-launcher.md.j2, dashboard.html.j2)

**What team-forge does NOT ship:** domain-specific agents (combiner-skeptic, combiner-librarian, ui-designer, ml-model-trainer, etc.) and domain-specific team launchers (combiner-team, combiner-peer-debate). Those are FORGED into the target project's `.claude/` at Phase 4 from templates. They belong to the project, not the extension.

Installed once, used across every repo we own.

## Why it exists

Hand-writing agent definitions + launcher skills for every project (HERC + Dynamic IC + AE Denoising + GBM + Barra MVO) wastes effort. The agent-teams primitive lets a session spawn N persistent teammates with shared task list + mailbox — but you still have to declare them. team-forge generalizes the work.

**Prior art:** the combiner-research stack in `/Users/shirleyfu/8888/wjsl_trader`. Predates the agent-teams primitive but is the architectural pattern team-forge auto-emits.

## The agent-teams primitive bet + rehydrate protocol

team-forge targets agent-teams. We accept its experimental status + limitations and design around them.

**Verified limitations (from `docs/agent-teams-primitive-notes.md`):**
- No per-teammate memory out of the box
- No shared team-memory namespace
- Teammates evaporate on `/resume`
- Standard file tools only — coordination via Read/Write to shared `.claude/` files
- No locking primitives — race conditions are the user's problem

**The rehydrate protocol — load-bearing under v8:**

```
On /<team>-team:
  Main session adopts lead role (custom prompt per project).
  Lead reads .claude/team-forge/<team>/tracker/status.json
    + .claude/team-forge/<team>/runtime/<current-milestone>/{brainstorm,plan}-<latest-cohort>.md
    + .claude/team-forge/<team>/artifacts/<current-milestone>/*.md
  Lead spawns all roster teammates per the saved state.
  Each teammate receives in its spawn prompt:
    - its role + purpose
    - a pointer to the hub directory for context
    - which task ID it's resuming (if any)
  Work proceeds.

On /resume of an existing /<team>-team session:
  Identical to fresh launch (above) — teammates are re-spawned from disk.
  No assumption that pre-resume teammates exist.
```

**The single-writer rule (kept from HERC's existing pattern):** only the lead writes to `.claude/team-forge/<team>/runtime/` and `artifacts/`. Tracker writes only to `tracker/status.json`. Monitor writes only to `playground/`. Teammates write to ephemeral worktrees only. This eliminates the race-condition surface for the durable hub state.

## The 4-phase workflow — FIXED

| # | Phase | Driver | Output |
|---|---|---|---|
| 1 | **Brainstorm** | human + agent-team-aware brainstormer | Project brief + actively-elicited answers: other agents needed? what verification? what tracking? completion criteria? token budget? |
| 2 | **Plan** | human + agent-team-aware planner | High-level milestones + per-milestone: agent team expected, next-phase check, hard dependencies, before/after expectations, input/interface contract between this milestone and the next. |
| 3 | **Design** | multiple forge-design-agents (parallel; reciprocal review) | **One annotated `design.yaml`** — Phase 4 contract. Concrete roster, **asset discovery** (skills + agents) across codebase + plugins + configured reference libraries (e.g. ECC), comms patterns, escalation flow, rehydrate state declarations. Multi-agent review catches coverage issues, contradictions, missing fields. |
| 4 | **Forge** | AI auto | Reads `design.yaml` → emits agent `.md` files, team-launcher skill, `team-forge/<team>/{design.yaml, manifest.json, runtime/, artifacts/, tracker/status.json (initial empty state), playground/dashboard.html (initial rendered)}`, eval scaffolds. **The initial dashboard.html is rendered at forge time** from the template + the tracking spec from design.yaml, with empty state — user opens it immediately after forge completes and sees their team's starting page. |

Phases 1, 2, 3 each end with a human gate. Phase 4 is autogen.

## Five role types — FIXED

| Role | Does | Comms | Lifecycle |
|---|---|---|---|
| **Work** | Domain task | Mailbox to other workers + verifiers; receives task assignments from lead | Ephemeral; rehydrated on resume |
| **Verify** | Checks outputs before propagation | Talks to lead with verdicts; talks to tracker about status | Ephemeral; rehydrated |
| **Advise** | Unblocks work agents on hard problems | On-demand callable; reads memory + corpus | Ephemeral; rehydrated |
| **Tracker** | Aggregates project state per the `tracking:` spec in design.yaml. Maintains `status.json` with the project's `state_shape` + appends to `events[]`. | Only talks to verifier + lead | Ephemeral agent; **durable status.json** (rehydrate source of truth). Initial status.json is forge-emitted with empty state. |
| **Monitor** | Reads tracker + artifacts + runtime; rewrites `dashboard.html` per `tracking.dashboard_panels` spec. | Only reads tracker / talks to tracker / lead | Ephemeral; **durable dashboard.html** (Phase 4 emits initial rendered; monitor replaces on each update). |

**Role coverage rule (hard):** roster without all 5 roles is rejected at Phase 3. For one-shot project domains (e.g. single-build CLI work) where some roles have no natural function, a single teammate may carry multiple roles — this is documented in the design.yaml as `combined_roles: [tracker, monitor]` on that teammate. The 5-role coverage is per-team-as-a-whole, not per-teammate.

## Phase 3 contract — annotated `design.yaml`

The Phase 3 output is one file: `<project>/.claude/team-forge/<team>/design.yaml`. Heavily commented for human review; machine-parseable for Phase 4.

Schema (sketch — full version is the shipped `templates/design.yaml.j2`):

```yaml
project:
  name: <slug>                            # team prefix
  display_name: <human-friendly>
  target_repo: <abspath>
  domain: <quant-research|frontend|ml-research|backend-api|data-pipeline|custom>
  brief: |
    1-paragraph project brief (Phase 1 output)

milestones:
  - id: <slug>
    name: <human-friendly>
    output: <verifiable artifact>
    go_no_go: <explicit criterion>
    expected_team_size: <int>             # Phase 2 prediction
    next_phase_check: <criterion>
    hard_dependencies: [<milestone-id>, ...]
    interface_to_next: |                  # what this milestone hands off
      <prose description>

roster:
  - name: <slug>
    role: <work|verify|advise|tracker|monitor>  # or list if combined_roles
    purpose: |
      <prose description of what this teammate owns>
    shared_across_teams: <bool>           # default false
    skills: [<list of discovered skills>] # Phase-3 forge-agent search output
    # No tools_allowed — teammates get whatever they need

rehydrate:
  durable_state:
    - .claude/team-forge/<team>/tracker/status.json                            # source of truth — points to current brainstorm + team-plan
    - docs/team-forge/<team>/brainstorms/<current>.md               # KB, from status.json.current_brainstorm
    - docs/team-forge/<team>/team-plans/<current>.md                # KB, from status.json.current_team_plan
    - docs/team-forge/<team>/artifacts/<milestone-id>/*.md          # KB (narrative)
    - docs/team-forge/<team>/runtime/<milestone-id>/*.md            # KB (optional; iterative only)
    # Plus the agent-teams shared task list at ~/.claude/tasks/<team>/ — native, lead-managed.
    # Tracker history fields let lead reconstruct prior brainstorms/plans if needed for audit.
  respawn_order: [tracker, advise, verify, work, monitor]
  # No context_pointers block — read paths are convention-derived from team name + role.
  # Each teammate's spawn prompt (from the team-launcher skill template) tells the teammate
  # its role + team name; the teammate derives what to read from team-forge's universal layout.

tracking:                                  # per-project end-to-end tracking spec
                                           # Phase 3 forge-design-agents propose this from
                                           # roster + milestones + domain; human approves.
                                           # Tracker agent reads this at runtime to know what
                                           # to aggregate into status.json.
  state_shape:                             # fields in tracker/status.json
    - id: current_milestone
      type: string
      source: lead.plan_output
    - id: <metric-name>                    # project-specific (e.g. champion_sharpe for HERC,
      type: <numeric|string|list>          #                    components_built for frontend)
      source: <which-agent-reports-it>
    # ... domain-specific tracked state lives here
  events_to_log:                           # events tracker appends to status.json.events[]
    - milestone_started
    - milestone_completed
    - cohort_started                       # if domain has iteration
    - cohort_completed
    - verifier_verdict
    - agent_blocked                        # from verify-role agents
    - <domain-specific events>
  dashboard_panels:                        # what monitor renders in dashboard.html
    - milestone_timeline
    - team_roster + agent_status
    - <domain-specific panels — e.g. cohort_table for HERC, component_grid for frontend>

constraints:                              # project-specific facts the forge agent can't infer
  - <free-form bullets>

skill_discovery_results:                  # Phase-3 forge-agent codebase + plugin search output
  discovered_skills:
    project_local: [<list>]
    user_global: [<list>]
    plugins:
      team-forge: [<list>]
      superpowers: [<list>]                # if installed; reference only
  proposed_loadouts_per_teammate:          # what the forge agent proposes for human approval
    <teammate>: [<skill list>]
```

The design agent populates everything except the `project`, `milestones`, and `constraints` blocks — those are direct from Phases 1 and 2 + the human.

## Output layout — committed to project repo

```
<target_repo>/                                          ← committed to git
  .claude/                                              ← RUNTIME STATE (small, structured)
    agents/<team>-<name>.md                             ← teammate type definitions; skill loadouts from Phase-3 discovery
    agents/<shared-name>.md                             ← unprefixed if shared_across_teams: true
    skills/<team>-team/SKILL.md                         ← entry point: /<team>-team — custom per project
    team-forge/<team>/                                  ← THE TEAM'S RUNTIME HUB
      design.yaml                                       ← annotated; Phase 3 contract; Phase 4 input
      manifest.json                                     ← generated files + design-yaml hash
      tracker/
        status.json                                     ← single-writer: tracker only; rehydrate source of truth
                                                          (Phase 4 emits initial empty state from design.yaml's tracking.state_shape)
      playground/
        dashboard.html                                  ← single-writer: monitor only; user-facing
                                                          (Phase 4 emits initial rendered from template + tracking.dashboard_panels)
        dashboard-data.json

  docs/                                                 ← HUMAN-FACING KNOWLEDGE BASE
    team-forge/<team>/                                  ← audit trail + narrative artifacts (no skill-family namespace, no repo-name level)
      brainstorms/                                      ← REQUIRED dir · single-writer: lead only
        brainstorm-<session-id>.md                      ← e.g. brainstorm-2026-05-31.md, brainstorm-pivot1.md
                                                          PROJECT-LEVEL. Phase 1 produces the FIRST one.
                                                          Lead writes a new one when project pivots / re-understands.
      team-plans/                                       ← REQUIRED dir · single-writer: lead only
        team-plan-<plan-id>.md                          ← e.g. team-plan-v1.md, team-plan-v2.md
                                                          PROJECT-LEVEL. Phase 2 produces the FIRST one.
                                                          Lead writes a new one when scope shifts significantly.
      artifacts/<milestone-id>/                         ← user-facing narrative outputs as work happens
        verification-walkthrough-<iter-id>.md           ← verifier-agent walkthroughs
        section-conclusion-<step>-<iter-id>.md          ← lead's conclusions per step
      runtime/<milestone-id>/                           ← OPTIONAL · only for iterative milestones
        plan-<iter-id>.md                               ← per-iteration plan, lead-written audit trail
                                                          (one-shot milestones don't need this — the shared
                                                           task list is the lead's planning surface)
      README.md                                         ← entry point for human reviewers; auto-generated by Phase 4
                                                          links to CURRENT brainstorm + CURRENT team-plan
```

**Current-pointer state** lives in the tracker's `status.json` (`.claude/team-forge/<team>/tracker/status.json`):

```json
{
  "current_brainstorm": "brainstorms/brainstorm-2026-05-31.md",
  "current_team_plan": "team-plans/team-plan-v2.md",
  "brainstorm_history": ["brainstorms/brainstorm-2026-05-15.md", "brainstorms/brainstorm-2026-05-31.md"],
  "team_plan_history": ["team-plans/team-plan-v1.md", "team-plans/team-plan-v2.md"],
  "current_milestone": "phase-b",
  ...
}
```

Monitor's dashboard surfaces both current pointers + history. README.md at the team root is a human-readable index — lead writes/updates it when a new brainstorm or plan supersedes the previous (with a one-line "why we pivoted").

  agent_evals/<team>/                                   ← per-agent eval scaffolds

~/.claude/                                              ← USER-GLOBAL, created by Claude Code at runtime
  teams/<team>/config.json                              ← team runtime state (do NOT pre-author)
  tasks/<team>/                                         ← shared task list (lead-managed at runtime)
```

**The split rationale:** `.claude/team-forge/<team>/` holds small, structured runtime state (JSON files, the contract YAML, generated dashboard HTML). `docs/team-forge/<team>/` holds the human-readable knowledge base — brainstorm narratives, plan walkthroughs, verifier conclusions, audit trail. Human content goes under `docs/`, not `.claude/`.

**Durable paths are domain-named, repo-relative, and framework-neutral.** The KB root is `docs/team-forge/<team>/` — one project-owned root, no skill-family namespace (no `superpowers/`), and no repo-name level (we are already inside that repo; `target_repo_basename` never appears in a durable path). Framework-internal identifiers (phase/task IDs) live ONLY in the runtime ledger (`status.json`, `TASKS.yaml`); they never leak into durable, portable, human-facing surfaces. See "Naming discipline" below.

**No `.claude/hooks/` dir.** No `.claude/workflows/` dir (Workflow dropped as runtime primitive). No `tools_allowed` declarations on teammates.

## Naming discipline (framework-internal IDs vs durable surfaces)

**Root cause this prevents:** framework-internal identifiers leaking into durable, portable, human-facing surfaces. A future engineer reading `git blame` should never hit "honour D5 write-only-first" with no decoder.

1. **Phase / milestone / task IDs are internal-ledger-only.** IDs (`m1`, `T5b`, `F12`, …) appear ONLY in the runtime ledger — `status.json`, `TASKS.yaml`, the `design.yaml` contract. They are the framework's internal addressing, not a public vocabulary.
2. **Outward surfaces use the human-readable NAME, never the ID.** Commit messages, PR titles, code comments, and KB doc filenames/headers reference the milestone/task *name* (e.g. "post-process-only runner"), not its ID (`T5`). If an ID is genuinely needed for cross-reference, the artifact must carry a glossary mapping IDs → names so it is self-decoding.
3. **Artifact filenames are content-descriptive:** `<subject>-<artifact-kind>.md` (e.g. `migration-plan.md`, `runner-design.md`, `deletion-safety-cert.md`). Banned: generic names (`open-decisions.md`, `design-3.md`, `team-plan-v1.md` is acceptable only because it is a project-level required artifact with a version).
4. **Directory names are descriptive slugs, never phase IDs.** `artifacts/<milestone-slug>/` where the slug is meaningful (`post-process-runner/`), never an opaque code (`artifacts/t5/`). Milestone/task IDs in `design.yaml` SHOULD themselves be descriptive slugs so this falls out for free.

The forge skill and the team/workflow launchers carry the operational reminder; this section is the rationale of record.

## Adversarial critique is a REQUIRED phase

The pattern that repeatedly catches **load-bearing** errors (not cosmetics) is
**fan-out → synthesize → adversarial-critique → revise.** In the alpha-variant-system run it caught a
silent signal-flip (per-family transform asymmetry), a non-identity-base double-apply, standalone
wrappers that couldn't use the post-process-only runner, and silent-success-on-failed-write — none of
which a passing gate set surfaced on its own.

So the critic stage is **required, not optional**, on any non-trivial change (plan, migration, PR,
medium/high `blast_radius` task): at least one pass whose explicit job is to REFUTE the result before
it propagates, with its verdict recorded in the artifact. The phase skills' self-review checklists and
the launchers' verification fan-out are where this is enforced; a green gate set without a critic pass
is not "verified."

## The team-forge extension — what we ship

```
team-forge/                                       ← OUR extension repo (generic only)
  .claude-plugin/{plugin.json, marketplace.json}
  skills/                                         ← agent-team-aware patterns
    team-forge:brainstorming/SKILL.md             ← Phase 1 (active interrogation variant)
    team-forge:writing-plans/SKILL.md             ← Phase 2 (with hard-dependency interrogation)
    team-forge:design/SKILL.md                    ← Phase 3 pattern for forge-design-agents
    team-forge:forge/SKILL.md                     ← Phase 4 emission pattern
    team-forge:tracker/SKILL.md                   ← tracker-role generic pattern
    team-forge:monitor/SKILL.md                   ← monitor-role generic pattern
    team-forge:rehydrate/SKILL.md                 ← /resume rehydrate protocol for lead
    team-forge:teardown/SKILL.md                  ← lifecycle close: archive ledger, prune worktrees,
                                                    remove launcher+trigger, classify durable vs ephemeral
  templates/                                      ← Phase 4 emits from these
    design.yaml.j2                                ← Phase 3 schema skeleton
    agent.md.j2                                   ← per-agent emission template
    team-launcher.md.j2                           ← <team>-team skill template (generic)
    domain-launcher.md.j2                         ← optional: pattern for domain-toolkit launchers
                                                    (combiner-team is one instance, forged INTO project)
    dashboard.html.j2                             ← monitor's playground template
  hooks/session-start                             ← slim; announces extension availability
```

**No domain agents in the extension.** No `combiner-skeptic.md`, no `combiner-librarian.md`, no `combiner-team/SKILL.md`, no `combiner-peer-debate/SKILL.md`. Those are FORGED into the target project at Phase 4 (using templates the extension ships) and live in `<target_repo>/.claude/agents/` and `<target_repo>/.claude/skills/`.

Forged teammates' `skills:` references look like `team-forge:brainstorming` for generic patterns and `<team>-<domain-skill>` for project-local skills. **The dependency contract:** every forged team requires team-forge installed in the target repo. The team-launcher skill checks at startup and fails loudly if missing.

**"Shared across teams" — clarified:** when a roster entry has `shared_across_teams: true` in design.yaml, it means "shared across forged teams in the SAME project's `.claude/`." Example: HERC forges `combiner-skeptic.md` into `wjsl_trader/.claude/agents/`. Dynamic IC (also in wjsl_trader) later gets forged and detects the file exists — it reuses it instead of overwriting. NOT shared at the team-forge extension level.

## Memory model — file-based coordination

Per verification: **no native memory for agent-team teammates.** We design our own architecture:

| Layer | Owner | Storage | Notes |
|---|---|---|---|
| Per-teammate runtime context | Each teammate | In-context only (ephemeral) | Gone on `/resume`; teammates must respawn with explicit context from the hub + KB |
| Shared team narrative state (audit trail / KB) | Lead (single-writer) | `docs/team-forge/<team>/{brainstorms/, team-plans/, artifacts/, runtime/?}` | Multiple brainstorms + team-plans accumulate over the team's lifetime (project pivots, scope shifts). Tracker's `status.json` holds `current_brainstorm` + `current_team_plan` pointers + history arrays. artifacts/ narrative outputs as work happens. runtime/ optional — iterative milestones only. README.md links to current. |
| Project status (structured) | Tracker (single-writer to its file) | `.claude/team-forge/<team>/tracker/status.json` | Rehydrate source of truth (persists on disk). **Ephemeral / gitignored** — runtime state, not git-tracked; the durable record is the KB + (on teardown) `final-ledger.json`. |
| User-facing dashboard | Monitor (single-writer to its file) | `.claude/team-forge/<team>/playground/dashboard.html` | Replaced on each update; **ephemeral / gitignored**. Generated from status.json — committing it would be a tracked artifact derived from ignored state (retro #1687, item 11). Forge emits `hub/.gitignore` ignoring `playground/` + `tracker/status.json` so both are uniformly ephemeral. |
| Design contract | Phase 4 forge (write-once) | `.claude/team-forge/<team>/design.yaml` | Authoritative; Phase 4 input + ongoing reference |

Single-writer per file = no locking needed. Multi-writer scenarios are rejected at design time.

## Validation — verifier agents + tracker, no hooks

| Concern | Who validates |
|---|---|
| Output correctness before propagation | Verify-role agents (smoke-tester, reviewer, analyzer) |
| Adversarial review of proposals | Verify-role agent (skeptic) |
| Project status truth | Tracker — aggregates from verifier verdicts + lead's plan outputs |
| Surfacing status to user | Monitor — reads tracker, updates dashboard |
| Role coverage at runtime | Implicit — all 5 roles spawned at team launch (and re-spawned on resume) |
| Handoff schema compliance | Receiving agent rejects malformed input; verifier flags deviations |

`TaskCreated` / `TaskCompleted` / `TeammateIdle` hook events fire natively in Claude Code — team-forge attaches nothing.

## HERC as worked example (v8 roster)

The HERC stack as it would be forged under v8:

- **Lead:** main session (adopts via `/herc-team`)
- **Work:** herc-implementer
- **Verify:** herc-analyzer (dual-mode), herc-smoke-tester, combiner-skeptic (forged into `wjsl_trader/.claude/agents/`; `shared_across_teams: true` so Dynamic IC reuses it; no skill loadout)
- **Advise:** combiner-librarian (forged into `wjsl_trader/.claude/agents/`; `shared_across_teams: true`; no skill loadout)
- **Tracker:** herc-tracker — aggregates cohort state, milestone progress, token spend
- **Monitor:** herc-monitor — writes `team-forge/herc/playground/dashboard.html`

**Rehydrate behavior:** on `/resume`, the lead reads `team-forge/herc/tracker/status.json` (current champion, current cohort_id, active threads, probation state), spawns all 7 teammates, hands each its respective context pointer. Work continues.

**Real HERC gaps that v8 surfaces (not retro-justification):**
- No design-review verifier between MERGE and EXECUTE — config errors surface at runtime
- Memory-write authority is single-writer in HERC today (already correct); the v8 framing formalizes the rule
- Existing combiner-team skill manually adopts lead role + spawns teammates via natural language; v8 makes this a typed pattern

**Discarded as circular (per v7 review):** "No tracker" and "No monitor" are NOT pre-existing HERC gaps. They are v8 role inventions. HERC reached its current champion using memory-file reads for tracking. Whether v8's tracker/monitor abstraction is worth the role-count tax is a judgment we accept as part of v8.

## How team-forge relates to Superpowers

| | Superpowers (upstream) | team-forge (our extension) |
|---|---|---|
| Provides | Single-session procedural skills | Forging capability + shared skills + shared agents + combiner toolkit + templates |
| Output | Skills installed at user-global or plugin scope | Files committed to the target project + team-forge hub directory |
| Customization | None per project | Every team shaped by domain |
| Multi-agent awareness | None | Agent-team-aware throughout |
| Relationship | Reference / inspiration | Our agent-team-aware sibling; first-class skill source for forged teammates |

## Repo location

Staging + dev: `/Users/shirleyfu/8888/team-forge/` (git: `main`). Published private at `shirleyfuxw/team-forge`.

**Branches:**
- `main` — the lean, shipped extension (skills, templates, tools, hooks, manifests).
- `design-history` — preserves the full design-process trail (8 SCOPING iterations of research: workflow-integration analysis, the v7 critical review, the slim/markdown/declarative design-doc drafts, example workflow `.js`, and the two concept/dashboard playground HTMLs). Browsable but not shipped.

Verified-facts reference kept in `main`: `docs/agent-teams-primitive-notes.md` (the agent-teams primitive's real memory + lifecycle behavior).

## Open decisions (post-v8 freeze)

Implementation-level only. No architectural reshuffling.

1. **Run the forge skill via Claude itself** (vs `tools/forge.py`) on a real project — confirm the agent-procedural path matches the deterministic renderer.
2. **Larger-team forge test** (10+ agents, real domain) — the greeter fixture is minimal.
3. **Idempotent regeneration** — forge currently refuses if non-shared files exist; post-MVP it should diff against the prior manifest and update in place.
4. **CI** — run `tools/forge.py` against the `tests/` fixture on every push.

## Status

**v0.1.0 — MVP feature-complete, end-to-end forge validated, then put on a 4.8 diet.**

Shipped on `main`:
- ✅ 7 skills (4 phase + rehydrate + tracker + monitor); each phase skill has a context-isolated `references/review.md`
- ✅ 4 logic-free `{{VAR}}` templates
- ✅ `tools/forge.py` — deterministic renderer (accepts a design.yaml path arg)
- ✅ End-to-end forge validated on the 6-agent greeter fixture (`tests/`)
- ✅ 4.8 diet: `forge` skill defers to `forge.py` (277→103 lines); review checklists trimmed to non-guessable / hard-abort checks; playgrounds + research specs moved to the `design-history` branch

The irreducible convention layer (design.yaml schema, the rehydrate protocol, 5-role coverage, single-writer authority, tracker/monitor patterns) is what remains in `main`. Everything a capable model can derive on its own was cut.
