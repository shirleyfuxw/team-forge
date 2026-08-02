# team-forge

Claude Code plugin whose product is a **verified problem contract**: the user's
actual problem, interrogated — plus verification steps the model can run without
the user present. Agent teams, workflow loops, and launchers are **opt-in
machinery** generated only when the contract demands them. The **dashboard** is
kept as the agent-behavior observation surface: the model verifies the work, the
human observes the model. The full argument: [GOAL.md](./GOAL.md).

**Status:** v0.10.0 — the contract pivot
([docs/specs/2026-08-01-contract-pivot-plan.md](./docs/specs/2026-08-01-contract-pivot-plan.md)).
Four skills, one deterministic renderer, one runtime. The old 4-phase pipeline
(brainstorm → plan → design → forge) and the standing tracker/monitor roles are
retired; [SCOPING.md](./SCOPING.md) / [WORKFLOW-SCOPING.md](./WORKFLOW-SCOPING.md)
carry errata banners and remain as historical record.

## The shape

```
team-forge:contract   →  contract.yaml       (the product: problem + checkable done_when)
      │ route: direct-execution (DEFAULT) — work it now with existing skills/subagents
      │ route: machinery (must be earned)
      ▼
team-forge:design     →  design.yaml         (archetype, roster/tasks, gates, skill gaps)
      ▼
tools/forge.py        →  emitted files       (deterministic render — not a skill)
      ▼
/<team>-workflow | /<team>-team               (~25-line thin pointer)
      ▼
team-forge:run        →  the lead loop       (policy lives HERE, plugin-propagated)
```

- **`team-forge:contract`** — interrogates the problem behind the ask and designs
  its verification: every `done_when` entry carries a `check:` the model can run;
  what can't be checked yet lives in `open_items`. Lint: `tools/contract_lint.py`
  (prose entries, restated checks, and human-activity checks fail). Ends by
  routing — **direct execution is the default**; machinery must cite an earned
  criterion (a check with no backing capability, cross-session/unattended work,
  genuine fan-out).
- **`team-forge:design`** — opt-in machinery design. Absorbs the machinery
  interrogation (archetype work-shape triage, roster, tracking, budget), runs the
  3-lens parallel design agents + asset discovery, produces `design.yaml`
  (which references the contract — forge derives the goal directive from it),
  and ends by running the renderer.
- **`tools/forge.py`** — deterministic emission (validation, panel-id registry,
  protected-branch pre-flight, forge-time consumer exercise of the dashboard
  payload). `--check` reports template drift for a forged team; `--resync`
  regenerates template-derived files preserving the ledger.
- **`team-forge:run`** — the shared runtime: goal-directive autonomy, the five
  paid-for lead-discipline rules, dispatch/fan-out policy, `fresh_session`
  handoffs, re-plan, naming discipline — once, for every team. Shape loops in
  `references/` (sequential / drain / team; `drift-audit.md` is the dashboard's
  cold verifier). Per-team launchers are thin pointers, so runtime policy
  updates with the plugin instead of going stale in baked copies.
- **`team-forge:teardown`** — the lifecycle close: archive the ledger, prune
  worktrees, remove the pointer + profiles via the manifest.

## What a forge emits (machinery route)

```
<target_repo>/
  .claude/
    agents/<team>-*.md                  # worker/advisor profiles (native memory) or roster
    skills/<team>-workflow/SKILL.md     # ~25-line pointer to team-forge:run
    team-forge/<team>/
      design.yaml · TASKS.yaml · manifest.json
      tracker/status.json               # lead-written ledger + contract-derived goal_directive
      gates/                            # gate scripts you author at runtime
      skill-drafts/<gap>/SKILL.md       # DRAFTs pending human promotion
      playground/gen_dashboard.py + dashboard.html   # when the run earns a dashboard
  docs/team-forge/<team>/
    contract.yaml                       # the product, stashed durably
    brainstorms/ team-plans/ artifacts/ runtime/ README.md
```

The dashboard renders the **contract strip** — statement + each `done_when` with
its check — above every panel; one-shot workflows default to no dashboard
(ledger-only), and the run skill dispatches a **drift audit** (cold agent:
pull authoritative state, reconcile, report) at milestone/cycle boundaries. A
standing monitor exists only for recurring/unattended workflows (enforced) or
persistent team rosters.

## Skills are the product (unchanged, sharpened)

A needed check with no backing capability is a **skill gap** — recorded in
design.yaml with a trigger-first description and a runnable acceptance check;
forge emits one DRAFT scaffold per gap under `skill-drafts/`, and a human
promotes it to `.claude/skills/` after the acceptance runs green. Gates that
call an unpromoted skill fail-closed. Under the pivot this is the heart: a
`kind: verification` skill is a contract verification step made durable.

## Verification

```bash
python3 tests/check_dashboard.py
```

Forges all 3 fixtures and runs both halves of the harness: **emission**
(self-contained dashboard, contract strip, thin pointers, panel registry, 3
negative checks incl. protected-branch abort) and **elicitation**
(`tests/check_contract.py` — the contract lint's bar against good/bad fixtures).

## Requires

- Claude Code; `python3` + `pyyaml` for the renderer and lint.
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` only for the `team` archetype
  (persistent rosters); the workflow archetype and direct execution don't need it.

## Install

**From GitHub (teammates — use this):**

```bash
/plugin marketplace add shirleyfuxw/team-forge
/plugin install team-forge@team-forge-dev
```

Pin a release if you want a known-good version — [releases](https://github.com/shirleyfuxw/team-forge/releases)
(current: `v0.10.0`). Update later with `/plugin marketplace update team-forge-dev`.

**From a local clone (development):**

```bash
/plugin marketplace add ~/8888/team-forge
/plugin install team-forge@team-forge-dev
```

## Reference libraries (prior art, not installed)

Phase-3 asset discovery can mine pinned external corpora (e.g. ECC —
`reference-libraries/ecc.yaml`) without installing them: fetched on demand to
`~/.cache/team-forge/`, domain-filtered, proposed as **adapt** candidates with
provenance. Pins advance only via the weekly `bump-references` PR.

## Roadmap

- [x] Contract pivot: contract skill + lint + derived goal directive + generic
  runtime + thin pointers + contract-strip dashboard (v0.10.0)
- [x] Capability ablation: forge/rehydrate/tracker/monitor skills retired
- [ ] Dogfood: a real project end-to-end through contract → direct execution,
  and one through the machinery route
- [ ] Goal-enforcement hooks (opt-in Stop-hook + post-compaction re-injection)
- [ ] CI: run the harness on every push

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
