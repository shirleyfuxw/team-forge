---
name: team-forge:writing-plans
description: |
  Use when starting Phase 2 of the team-forge loop (after brainstorming produces
  a brief), OR when the lead needs to revise the team-plan because the project
  pivoted. Agent-team-aware planning with active interrogation about hard
  dependencies, interfaces between milestones, and per-milestone expected team
  size. Writes a dated, content-descriptive plan (`<slug>-plan-<YYYY-MM-DD>.md`) to the KB.
---

# team-forge:writing-plans — Phase 2 (or runtime plan revision)

The agent-team-aware variant of writing-plans. It produces a project-level plan
that names milestones with their hard dependencies + interfaces + expected team
sizes — NOT a detailed task list (the shared task list handles that at runtime).

## When to use

- **Phase 2 of a fresh team-forge run** — right after brainstorming
- **Runtime, mid-project** — when the scope shifts significantly enough that the
  current team-plan no longer maps to reality
- **Post-completion / follow-on** — the project's milestones are all done, but a new
  round of improvement, hardening, or extension work is warranted. This is a *new* dated
  plan whose slug names the new focus (e.g. `-improvements-`, `-hardening-`), NOT a
  revision of the finished one.

## Inputs

- The brainstorm document (the latest `brainstorms/brainstorm-<session-id>.md`)
- The user (interactive)
- If runtime: the current team-plan (the tracker's `current_team_plan` pointer) to revise from

## What you produce

A markdown file at `docs/team-forge/<team>/team-plans/<slug>-plan-<YYYY-MM-DD>.md`,
where `<slug>` is a short content-descriptive slug (the project/team slug for the first
plan; the *focus* for a later plan — e.g. `hardening`, `phase2`, `perf-improvements`) and
`<YYYY-MM-DD>` is today's date. Examples:

- First plan:            `combiner-v3-rewrite-plan-2026-07-02.md`
- Post-completion round: `combiner-v3-rewrite-improvements-2026-08-15.md`

**Naming rules:**
- **Meaningful + dated, never generic.** Never write `team-plan-v1.md`. The name must
  describe the plan's subject/focus AND carry the date it was cut.
- **Same-day revision collision:** if that exact filename already exists, append `-v2`,
  `-v3`, … (`…-2026-07-02-v2.md`). A revision on a later day just uses the new date.
- **"Current" is tracked, not encoded in the name.** The tracker's `current_team_plan` +
  `team_plan_history` are the source of truth for which plan is live and the revision
  order — the filename needs no global version counter.

## Procedure

### Step 0 — Survey the existing team KB (both archetypes, do this first)

Before refining anything, read what the team already has, so the plan builds on prior work
instead of duplicating or contradicting it:

- List `docs/team-forge/<team>/{team-plans,brainstorms,artifacts,runtime}/` and read the tracker's
  `status.json` for `current_team_plan` + `team_plan_history` (and `current_brainstorm`).
- Read the **current** team-plan (if any) and the **current** brainstorm; skim recent narrative
  artifacts (design walkthroughs, verification walkthroughs, decision records) for work already
  done or gated.
- **Duplication + correctness check** — answer explicitly before writing anything new:
  - Is a milestone/task you're about to add **already covered** by an existing plan or a done
    artifact? Reference/build on it — don't re-plan completed work.
  - Does the new plan **contradict a prior decision or a gated result**? Surface the conflict and
    reconcile with the user; a re-plan preserves gated/committed work, it doesn't silently discard it.
  - For a **post-completion / follow-on** plan: scope it to the *new* work only, citing what the
    prior plan already delivered.
- If there is no prior plan (fresh Phase 2) → note it and proceed from the brainstorm.

Record what you're building on (or superseding) in the plan's `## Revision notes`.

> **Archetype branch.** If Phase 1 set `archetype: workflow`, follow **"Workflow archetype —
> the task list"** below *instead of* the milestone Steps 1–5 (then do Steps 6–7). The
> milestone procedure is the `team` path. Step 0 above runs first either way.

### Workflow archetype — the task list (the proto-TASKS.yaml)

Phase 2 for a workflow produces an **ordered task list**, not milestones. For each unit of work, with the user:

1. **Verifiable output?** — a file path / artifact / metric.
2. **Depends on?** — which task ids must be `done` first (the DAG must stay acyclic).
3. **Blast radius?** — `low | medium | high`; this drives the `gate_set` (Phase 3 finalizes it).
4. **Inline or dispatched?** — default `inline` (the lead codes it); `worker` only for
   fan-out / context-isolation / independent verification.
5. **Interface to next** — what state the next task inherits.

Sketch the **gate vocabulary** alongside — Phase 3 finalizes it by reading the repo's
verification surface (test suites, CI, build targets, invariants; W5). Expect to re-cut the
list as implementation reveals the true shape (W7) — it is a hypothesis, not a contract.

**Parallel-drain shape:** there is no authored task list — instead specify the `queue`
(eligibility query, triage/routing predicate, wave size, routes) and, if recurring, the
schedule + cycle box + `unattended` flag.

Write the task list (or queue spec) into `team-plans/<slug>-plan-<YYYY-MM-DD>.md` (see the naming rules above) — it becomes the
proto-`TASKS.yaml`. Then go to **Step 6** (tracker update) and **Step 7** (confirm). Skip
Steps 1–5.

### Step 1 — Re-read the brainstorm   *(team archetype path)*

Read the current brainstorm doc. Note the milestone sketch + completion criteria
+ token budget. These are your starting context.

### Step 2 — Refine each milestone

For each milestone in the brainstorm's sketch, ask the user:

1. **Verifiable output?**
   > "What's the verifiable output for `<milestone-id>`? Be concrete — a file path, a metric threshold, a deployed artifact."

2. **Hard dependencies?**
   > "Which other milestones must be done before this one starts? Empty list is fine."

3. **Interface to next milestone?**
   > "When this milestone is done, what state must exist for the next milestone to begin? Describe in 2–3 sentences."

4. **Expected team size?**
   > "Roughly how many teammates are active during this milestone? (Doesn't have to be exact — Phase 3 will design the roster precisely.)"

5. **Next-phase check?**
   > "What's the human go/no-go check between this milestone and the next?"

Capture each answer. If the user is vague, push for specifics ("what's the unit?",
"file path or commit hash?"). Don't fabricate.

### Step 3 — Cross-check dependencies

Now look across all milestones. Ask:

> "Are there any milestones that should run in parallel? Are dependencies cyclic
> (which means the design needs revision)? Are there milestones that became
> redundant after refining?"

Cyclic dependencies → push back to user; one of them needs to be re-scoped or merged.

### Step 4 — Decide iteration shape per milestone

For each milestone, ask:

> "Is this milestone iterative (multiple cohorts/passes) or one-shot? For
> iterative milestones, what's a rough iteration count or end condition?"

Iterative milestones will use per-iteration plan files at runtime
(`runtime/<milestone-id>/plan-<iter-id>.md` — see SCOPING.md). One-shot milestones
don't need that — the agent-teams shared task list IS the per-iteration planning surface.

### Step 5 — Write the team-plan document

Create `docs/team-forge/<team>/team-plans/<slug>-plan-<YYYY-MM-DD>.md` (naming rules above):

```markdown
# <Project name> — Team Plan (<YYYY-MM-DD>)

Written <ISO-timestamp> by the lead (`<orchestrator-name>`). Derived from
`brainstorms/brainstorm-<session-id>.md`.

## Project recap (1 paragraph)

<re-state the goal from the brainstorm, for grounding>

## Scope figures (verified vs estimated)

Every quantitative scope claim goes here, in this table — separate VERIFIED from ESTIMATED.
A figure is **verified** only if it came from running a command (a `grep -c`, a query, a count),
with that command cited. Everything else is an **estimate** and is labelled as such.

| Figure | Value | Status | How obtained |
|---|---|---|---|
| <e.g. files in scope> | <n> | verified / estimated | <command run, or "rough guess — to be closed"> |

**Do not state a firm headline number until its counts are closed (all VERIFIED).** A headline like
"~11,600 files" that turns out to be mostly dead archive (real surface ~1,069) is a planning defect —
it mis-sizes the team and the budget. If a count is not yet verified, write the milestone around the
*verified* surface and flag the estimate as open.

## Milestones

### <milestone-1.id> — <milestone-1.name>

- **Output:** <verifiable output>
- **Go/no-go:** <criterion>
- **Hard dependencies:** <list, or "none">
- **Interface to next:** <2–3 sentences>
- **Expected team size:** <int>
- **Iteration shape:** one-shot | iterative (rough count: <N>)
- **Next-phase check:** <human go/no-go>

### <milestone-2.id> — <milestone-2.name>

... (same shape)

## Cross-milestone notes

- Parallel-runnable: <list pairs or "none">
- Critical path: <ordered milestone IDs>
- Token budget allocation: <rough split per milestone, summing to brainstorm's total>

## Carry-overs from brainstorm

(Anything the brainstorm flagged as uncertain that didn't get resolved here.
Phase 3 will need to decide these.)

## Revision notes

(If this plan revises or follows on from an earlier one, name the prior plan file and
list what changed and why. The tracker's `team_plan_history` holds the full ordering.)
```

### Step 6 — Update the tracker

After writing the file, send the tracker a message:

```
plan_update:
  current_team_plan: <relative-path-to-team-plan-file>
```

The tracker will append `team_plan_revised`, update `current_team_plan` and
`team_plan_history`.

### Step 7 — Confirm with the user

Show the user the team-plan doc and a 2-sentence summary of milestone shapes.
Ask if they approve to move to Phase 3 (Design).

## What this skill is NOT

- Not a task list. Don't enumerate sub-tasks per milestone. That's the runtime
  task list's job.
- Not a design. Don't pick the roster, name teammates, or list skills. That's Phase 3.
- Not autonomous. Every milestone needs the user's input.

## Failure modes

- **Cyclic dependencies declared** → push back to user; refuse to write the plan with cycles
- **Vague verifiable outputs** → push for concrete; "works well" is unacceptable
- **Unsubstantiated scope headline** → a firm count with no verifying command is an estimate; label it as such in the Scope-figures table and size the plan off the verified surface. Do not headline an unclosed count.
- **User wants to skip ahead to Phase 3 without naming dependencies** → tell them dependencies are mandatory; offer to mark all as `[]` only if they explicitly say so


## Output review

The review checklist for this phase lives at `references/review.md` — extracted from this skill so a separately-dispatched **review subagent** can load just the criteria without the full procedural skill body (context isolation).

**Two equivalent ways to run the review:**

1. **Inline (lighter, lead does it)** — read `references/review.md` yourself, run the checklist against the file(s) you just produced, surface ✓/✗ results to the user before the approval ask.

2. **Subagent (more isolated, fresh context)** — dispatch a subagent with the prompt:
   > "Review the output at `<path-to-output-file>` against the criteria in `references/review.md` of the team-forge `<this-skill-name>` skill. Report the checklist as a ✓/✗ list, then name any specific gaps for each ✗."
   The subagent reads only the criteria file + the output — no other team-forge context required.

Either path produces the same checklist output. The subagent path is preferable when the lead's context window is large enough that adding the review work would crowd it, or when a colder/independent verdict is wanted.

After the review (regardless of path), surface results to the user and ask: approve, revise, or abort. **Do not auto-pass on a hard-abort trigger** (those are documented in `references/review.md` per phase).
