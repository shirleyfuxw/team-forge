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
[v0.12.0](https://github.com/shirleyfuxw/team-forge/releases); update with
`/plugin marketplace update team-forge-dev`.

## Use

Start every engagement the same way:

```
Use team-forge:contract — I want to <your ask>.
```

You don't have to name it — a non-trivial ask whose finish line is still fuzzy
should reach it on its own. It interrogates the problem behind the ask and writes
`docs/team-forge/<team>/contract.yaml`: a problem statement, `done_when` entries
that each carry a `check:` the model can run (anything uncheckable is honestly
parked in `open_items`), and a `lead_decides` / `user_decides` split. The contract
is the goal, not the plan: it carries no task list or step sketch, because steps
written before the work starts cap the model's reasoning during it. A lint
(`tools/contract_lint.py`) enforces the bar — prose conditions don't pass, and
neither does an execution-steps key.

Then one of two routes, recorded in the contract:

- **`direct-execution` (default)** — the work is done right here with existing
  skills and subagents. Nothing is forged. The skill first hands you a
  paste-ready `/goal` line (`tools/goal_condition.py` renders the contract as
  Claude Code's own stop condition, so a separate evaluator keeps the session
  working until every check holds — you set it, the model can't). It closes by
  running every `done_when` check and reporting ✓/✗ (`tools/verify_contract.py`
  enumerates them, so none is skipped) — that step is what makes the contract
  *verified* rather than merely checkable.
- **`machinery` (must be earned)** — a needed check has no backing capability, the
  work spans sessions or runs unattended, or there's genuine fan-out. Then:
  `team-forge:design` (archetype triage, roster/tasks, gates, skill gaps) →
  `python3 tools/forge.py <design.yaml>` (deterministic emission) → launch with
  `/<team>-workflow` or `/<team>-team` → `run` → `evolve` → `teardown`.

A workflow team gets two entry points into the same runtime: `/<team>-workflow`,
and `claude --agent <team>-lead`, which carries persistent memory across runs so a
recurring drain stops re-deriving last cycle's lessons. The slash command starts
cold every time.

Forged runtimes are driven by **`team-forge:run`** — one shared skill holding all
lead policy (autonomy against the goal directive, discipline rules, dispatch and
gate rules), which updates with the plugin. The runtime reads exactly one file:
`tracker/status.json`, whose `plan` block is design-derived (re-baked by
`--resync`) and whose every other key is live state the lead owns. The per-team launcher is a ~25-line
pointer, so nothing policy-shaped goes stale in your repo. `team-forge:evolve`
runs at each cycle end and once more at close, turning the run's own artifacts
into lessons the next cycle starts from; `team-forge:teardown` then closes a
finished team out.

## What a forge emits

```
<target_repo>/
  .claude/
    agents/<team>-*.md                  # worker/advisor profiles (or team roster)
    agents/<team>-lead.md               # workflow lead, with persistent memory
    skills/<team>-workflow/SKILL.md     # thin pointer to team-forge:run
    team-forge/<team>/
      design.yaml · TASKS.yaml · manifest.json
      tracker/status.json               # ledger + contract-derived goal_directive
      gates/ · skill-drafts/            # your gate scripts; skill DRAFTs to promote
      playground/                       # dashboard, when the run earns one
  docs/team-forge/<team>/
    contract.yaml                       # the product, stashed durably
    lessons.md                          # lessons register, written by team-forge:evolve
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

## Evolve

A finished cycle already contains its own lessons; nothing was reading them.
`team-forge:evolve` runs at every cycle end of a recurring workflow and once more
at close, mining the ledger in `status.json` — event kinds that recur, an
`agent_blocked` that a later event resolves, gate failures carrying a root cause,
a budget line that blew past its soft target, `policy_adopted` rules the lead
applied mid-run that live in no file — plus every agent `MEMORY.md`, which native
per-agent memory writes but nothing ever harvested. The durable output is one
register per team: `docs/team-forge/<team>/lessons.md`, versioned against the
plugin, with an id per row that is never renumbered.

**Evidence, not impressions.** A lesson is *applied* only when a signal admits it
— the same normalized event kind seen twice or a payload counter that says so, a
block with a matching resolution, a gate failure with a root cause, a budget
overrun against its soft target, or a rule already adopted mid-run. Everything
else goes to a **Candidates** table and waits for a second sighting. One vivid
one-off is an anecdote, and anecdotes are what turn a register into folklore.

**Three layers, three autonomies.** L1 is team-local — the register,
`contract.yaml` open items, whichever agent memories the archetype forged, and
the team's gate surface (a workflow's gate scripts; a team's `go_no_go` criteria
are a `design.yaml` edit, so they land in L2) — and is auto-applied once the bar
is met. L2 is the project harness — `design.yaml` (then
`forge.py --resync`; a baked agent file is never hand-edited), `.claude/rules/`,
promoted skills — and lands on an `evolve/<team>-<date>` branch for you to
approve. L3 is team-forge itself, which is never edited from a target repo:
evolve writes `docs/team-forge/<team>/evolve/plugin-feedback-<date>.md`, and
filing it upstream is your call. An unattended cycle is L1-only; its L2
candidates queue for the next attended close.

**It prunes as well as accretes.** Every applied lesson names the check that
proves it and that check is run, against a snapshot that is restored if it fails.
Falsified rows are kept with what killed them — delete one and the next reader
re-derives the same wrong belief from the same plausible reasoning — and anything
that has gone several runs without a trace lands on the ablation queue, to be
deleted on a branch and re-added only if an observed failure asks for it.

## Development

```bash
git clone https://github.com/shirleyfuxw/team-forge && cd team-forge
/plugin marketplace add .                # local marketplace for development
python3 tests/check_dashboard.py         # emission + elicitation checks
python3 tests/check_evolve.py            # evidence admission + lessons register
```

`check_dashboard.py` forges three fixtures and asserts both halves of the
product: emission (self-contained dashboard with contract strip, thin pointers,
panel-id registry, nine negative checks) and elicitation
(`tests/check_contract.py`, the lint's bar against good/bad contract fixtures).
`check_evolve.py` covers the evolve phase — that the evidence bar admits what it
claims to admit, that a single anecdote reaches the Candidates table and no
further, and that the register survives a round trip. Each of its checks carries
a negative control: a check that stays green when its fix is reverted has tested
nothing, which this repo learned twice.

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
