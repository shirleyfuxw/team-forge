---
name: team-forge:contract
description: |
  Use when starting ANY team-forge engagement (this replaces the old Phase 1–2
  brainstorming + writing-plans skills), or when scope shifts mid-project.
  Interrogates the user's actual problem and designs its verification steps,
  producing docs/team-forge/<team>/contract.yaml — every done_when entry carries a
  check the model can run without the user. Ends by routing: direct execution
  (default) or the machinery path (design → forge), which must be earned.
---

# team-forge:contract — the problem + its verification steps

The product is a **verified problem contract** (see the repo's `GOAL.md`): what the
user is actually trying to solve, and how the model checks — mechanically, without
the user present — that it's solved. Rosters, launchers, and loops are optional
machinery downstream of this artifact, not the point.

The one load-bearing rule: **a done_when condition the model can't check isn't a
verification step yet — it's an open item.** `open_items` is the honest holding pen;
promoting an item into `done_when` means you found its check.

## What you produce

`docs/team-forge/<team>/contract.yaml` — a fixed-name machine contract (same class
as design.yaml / status.json; "current" is the file, history is git):

```yaml
contract: 1
problem:
  statement: |        # the problem, interrogated — not the user's first phrasing
  context: |          # optional: why now, what breaks without it
done_when:            # EVERY entry model-checkable
  - signal: "<the condition, human-readable>"
    check: "<HOW the model verifies it: a command / file predicate / gate id>"
open_items:           # real conditions with no check yet — blockers for done_when
  - "<condition — and what's missing before it can be checked>"
lead_decides: []      # standing approvals — act without asking
user_decides: []      # hard asks — always pause
route: direct-execution | machinery
tasks:                # OPTIONAL execution sketch (proto-TASKS.yaml) — only when
  - id: <slug>        # the work is multi-step; each with output/depends_on, and
    output: "..."     # dispatch/blast_radius when known. Machinery route refines
    depends_on: []    # it in design; direct execution works it as-is.
```

Validate before showing the user: `python3 <team-forge-extension>/tools/contract_lint.py
docs/team-forge/<team>/contract.yaml` — must exit 0. The lint is the quality bar
(prose done_when, restated checks, and human-activity checks all fail).

## Procedure

### Step 0 — Survey the existing KB

Read what already exists so you build on it instead of duplicating or contradicting:
`docs/team-forge/<team>/` (contract.yaml, brainstorms/, team-plans/, recent
artifacts) and, if a runtime exists, `.claude/team-forge/<team>/tracker/status.json`
(including `goal_directive`). Then answer explicitly:

- Is this problem already covered by the current contract? **Revise it** — don't
  start a parallel one.
- Does the new direction **contradict a prior decision or a gated result**? Surface
  the conflict to the user; never silently overwrite.
- Fresh project, no prior KB → note it and proceed.

### Step 1 — Interrogate the problem (not the ask)

Capture the user's goal paragraph **verbatim** first. Then interrogate — the first
phrasing is usually a symptom or a pre-chosen solution:

> "What breaks, and for whom, if this never happens?" · "Is <their stated task> the
> problem, or your current best guess at a fix?" · "What's explicitly OUT of scope?"

Write `problem.statement` as the question behind the ask. If the user's task framing
and the problem diverge, show them both and let them choose — that divergence is the
most valuable output of this step.

### Step 2 — Design the verification steps

For each completion signal the user names:

> "How would the model check that without you in the room? A command? A file that
> must exist / a grep that must come back empty? A gate that must run green?"

- Read the repo's **verification surface** (test suites, CI targets, invariants) —
  checks should reuse it. A needed check with **no backing capability** is a skill
  gap: record it in `open_items` now; the machinery route's design phase turns it
  into a `skill_gaps` entry with a runnable acceptance.
- Can't find a check → the condition goes to `open_items`, with what's missing.
  Do not pad `done_when` to look complete; a short honest list beats a long prose one.
- **Scope figures:** any count a done_when or task depends on is *verified* (cite
  the command) or *estimated* (label it). Never headline an unclosed count.

### Step 3 — Split the decisions

> "While the model works: what may it do without asking (standing approvals)? What
> must ALWAYS come back to you (irreversible, outward-facing, spend above a
> threshold)?" 

Record `lead_decides` / `user_decides` (empty lists are fine; absence is not).
Unlisted decisions default to: act if inferable from the contract + ledger, ask
otherwise. Include a budget line in `lead_decides`/`user_decides` if the user has one.

### Step 4 — Sketch execution (only as needed)

Multi-step work → sketch `tasks:` with the user (verifiable `output` +
`depends_on`; add `dispatch`/`blast_radius` when known; DAG must be acyclic). It's
a hypothesis, expected to be re-cut. Single-step work → omit `tasks` entirely.

### Step 5 — Write, lint, review

Write `contract.yaml`, run the lint (must exit 0), then run the review checklist
(`references/review.md` — inline, or dispatch a review subagent with just that file
+ the contract). Surface ✓/✗ to the user.

### Step 6 — Sync a live runtime (if one exists)

If a forged runtime is present, its `status.json.goal_directive` must match the
contract **before the first task of the new scope runs** — derive it (statement +
flattened done_when + decision split), log a `goal_revised` event with the delta.
A stale directive is the write-ahead failure aimed at yourself.

### Step 7 — Route and confirm

**`route: direct-execution` is the default.** Work the contract (and its task
sketch) in this session with existing skills/subagents; nothing is forged.

**`route: machinery` must be earned** — pick it only when the contract itself
demands standing machinery, i.e. at least one of:
- a needed check has **no backing capability** (skill gap → design/forge emit the
  draft + gate);
- the work **spans sessions** or runs **unattended/recurring** (needs launcher,
  rehydrate, ledger);
- genuine **fan-out or a standing roster** (parallel waves, persistent
  multi-perspective work).

Non-empty `open_items` that block a route choice → resolve or surface first.
Show the user the contract + the route and its earned criteria; they approve, or
redirect. If direct execution later outgrows itself (skill gaps appear, work spills
across sessions), come back, set `route: machinery`, and run the design phase then
— the fast path is an on-ramp, not a lock-in.

## What this skill is NOT

- Not a roster/tracking/archetype interrogation — that's the design phase's job,
  reached only via `route: machinery`.
- Not autonomous. The statement, checks, and decision split are the user's; you
  interrogate and draft, they own.

## Failure modes

- **User answers with a solution** → capture it, then still ask what problem it
  solves; record both.
- **"Works well" / "looks right" as a signal** → not checkable; push for the
  mechanical version or park it in `open_items`.
- **Every condition lands in open_items** → the problem isn't understood yet; say
  so plainly rather than forging ahead.
- **User declines a question** → record `declined` explicitly and proceed.
- **Cyclic `tasks` dependencies** → push back; refuse to write the sketch with a cycle.

## Output review

The checklist lives at `references/review.md` (standalone-loadable for a review
subagent). After the review, ask: approve, revise, or abort. Do not auto-pass a
hard-abort trigger.
