# team-forge

A Claude Code plugin that turns a vague ask into a **verified problem contract** —
your actual problem, interrogated, plus verification steps the model can run
without you — and then executes against it. Agent teams and workflow machinery
are opt-in extras, generated only when the contract earns them. Why this shape:
[GOAL.md](./GOAL.md).

## Install

```bash
/plugin marketplace add shirleyfuxw/team-forge
/plugin install team-forge@team-forge-dev
```

Needs `python3` + `pyyaml`. Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` only if
you use the persistent-roster `team` archetype. Releases:
[v0.10.0](https://github.com/shirleyfuxw/team-forge/releases); update with
`/plugin marketplace update team-forge-dev`.

## Use

Start every engagement the same way:

```
Use team-forge:contract — I want to <your ask>.
```

It interrogates the problem behind the ask and writes
`docs/team-forge/<team>/contract.yaml`: a problem statement, `done_when` entries
that each carry a `check:` the model can run (anything uncheckable is honestly
parked in `open_items`), and a `lead_decides` / `user_decides` split. A lint
(`tools/contract_lint.py`) enforces the bar — prose conditions don't pass.

Then one of two routes, recorded in the contract:

- **`direct-execution` (default)** — the work is done right here with existing
  skills and subagents. Nothing is forged.
- **`machinery` (must be earned)** — a needed check has no backing capability, the
  work spans sessions or runs unattended, or there's genuine fan-out. Then:
  `team-forge:design` (archetype triage, roster/tasks, gates, skill gaps) →
  `python3 tools/forge.py <design.yaml>` (deterministic emission) → launch with
  `/<team>-workflow` or `/<team>-team`.

Forged runtimes are driven by **`team-forge:run`** — one shared skill holding all
lead policy (autonomy against the goal directive, discipline rules, dispatch and
gate rules), which updates with the plugin. The runtime reads exactly one file:
`tracker/status.json`, whose `plan` block is design-derived (re-baked by
`--resync`) and whose every other key is live state the lead owns. The per-team launcher is a ~25-line
pointer, so nothing policy-shaped goes stale in your repo. `team-forge:teardown`
closes a finished team out.

## What a forge emits

```
<target_repo>/
  .claude/
    agents/<team>-*.md                  # worker/advisor profiles (or team roster)
    skills/<team>-workflow/SKILL.md     # thin pointer to team-forge:run
    team-forge/<team>/
      design.yaml · TASKS.yaml · manifest.json
      tracker/status.json               # ledger + contract-derived goal_directive
      gates/ · skill-drafts/            # your gate scripts; skill DRAFTs to promote
      playground/                       # dashboard, when the run earns one
  docs/team-forge/<team>/
    contract.yaml                       # the product, stashed durably
    brainstorms/ team-plans/ artifacts/ runtime/
```

**Observation:** the dashboard renders the contract — statement plus each
`done_when` and its check — above every panel, so you're always auditing the run
against what was promised. A dispatched **drift audit** (cold agent: pull
authoritative state, reconcile, report) verifies the ledger at milestone
boundaries; one-shot workflows skip the dashboard entirely and live in
`status.json` + `TASKS.yaml`.

**Skills are the product:** a needed check with no backing capability becomes a
`skill_gaps` entry with a runnable acceptance check; forge emits a DRAFT per gap
and a human promotes it to `.claude/skills/` once the acceptance runs green.
Gates that call an unpromoted skill fail-closed. These skills outlive the team.

## Development

```bash
git clone https://github.com/shirleyfuxw/team-forge && cd team-forge
/plugin marketplace add .                # local marketplace for development
python3 tests/check_dashboard.py         # the harness: emission + elicitation checks
```

The harness forges three fixtures and asserts both halves of the product:
emission (self-contained dashboard with contract strip, thin pointers, panel-id
registry, eight negative checks) and elicitation (`tests/check_contract.py`, the
lint's bar against good/bad contract fixtures).

Landing changes on an already-forged team: `python3 tools/forge.py --check <its
design.yaml>` reports both staleness axes — template drift and design drift —
then `--resync` lands them, re-baking the ledger's derived `plan` block and any
unpromoted skill draft while preserving live state. After revising a contract,
`--sync-goal` re-derives `goal_directive` into the live ledger and logs a
`goal_revised` event; it writes only that key. A bare re-forge over a live hub is **refused** — it would rewrite
`tracker/status.json` and reset task progress, gate results, and events; pass
`--force` only when you mean to discard that state. Design-phase asset discovery can also mine pinned reference
libraries (see `reference-libraries/`) without installing them.

Historical design docs — [SCOPING.md](./SCOPING.md),
[WORKFLOW-SCOPING.md](./WORKFLOW-SCOPING.md), and
[docs/specs/](./docs/specs/) — record how the project got here; errata banners
mark what's superseded.

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
