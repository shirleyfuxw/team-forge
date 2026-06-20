---
name: team-forge:brainstorming
description: |
  Use when starting Phase 1 of the team-forge loop OR when the lead needs to develop
  / revise the project's working understanding. Agent-team-aware brainstorming with
  active interrogation of the human about agent needs, verification, tracking,
  completion criteria, and budget. Writes a brainstorm-<session-id>.md to the KB.
---

# team-forge:brainstorming — Phase 1 (or runtime brainstorm revision)

This skill is the agent-team-aware variant of brainstorming. It's NOT a generic
"understand the goal" — it's specifically about developing the working understanding
needed to design a multi-agent team.

## When to use

- **Phase 1 of a fresh team-forge run** — kicking off a new project's design
- **Runtime, mid-project** — when the lead realizes the team's working understanding has shifted and needs to be re-grounded (e.g., the project pivoted, scope changed)

## Inputs

- The user (interactive conversation)
- If runtime: the current `brainstorms/brainstorm-<latest>.md` to revise from

## What you produce

A markdown file at `docs/superpowers/<project>/<team>/brainstorms/brainstorm-<session-id>.md`
where `<session-id>` is an ISO timestamp or a slug like `phase1-initial` or `pivot-1`.

## Procedure

### Step 0 — Triage the archetype (team vs workflow)

Before anything else, decide which forge archetype fits — it changes what Phases 2–4 produce.
Ask the **work-shape** question (the real distinguisher is *not* "is it parallel"):

> "As the work proceeds, do the agents each hold distinct, evolving context they defend
> across rounds (a research debate, competing approaches) — or is it a stream of tasks/items
> that get done, gated, and handed off, where each unit of work starts fresh?"

- **Fresh each unit / sequential or fan-out / gate-driven** → **`workflow`** archetype
  (refactor, migration, ticket-drain, bug-batch). Then pick `shape`:
  - **sequential-gated** — one deep task at a time (a refactor).
  - **parallel-drain** — many independent items triaged + drained in waves (a queue).
  - And the **`recurring`** modifier if it's cron-scheduled/unattended (no terminal "done").
- **Distinct persistent peer-context, sustained collaboration** → **`team`** archetype
  (research cohorts, design debate, exploration).

Record `archetype` (+ `shape`/`recurring` for workflow) at the top of the brainstorm doc.
**If `workflow`:** the rest of this skill still elicits goal + verification + completion +
budget, but Step 3 sketches a **task list + gate vocabulary** (not milestones + a roster),
and you additionally elicit the **integration branch** and what "done" means per task. Phases
2–4 then produce `tasks`/`gates`/`worker`/`ledger`, not `roster`/`tracking`.

### Step 1 — Establish the goal

Ask the user:

> "What's the high-level goal of this project? In one paragraph?"

Let them write it. Don't paraphrase yet. Capture verbatim.

### Step 2 — Active interrogation (the team-forge-specific part)

Now ask, in this order:

1. **Other agents needed?**
   > "Beyond the obvious work agents for the core task, are there specialized agents you have in mind? Domain experts? External tool wrappers? Anything project-specific that isn't covered by typical work/verify/advise roles?"

2. **Verification posture?**
   > "What kind of verification do you want? Adversarial peer review? Smoke tests against a baseline? Statistical significance checks? Visual regression? Schema conformance? Be specific about what 'good' looks like."

3. **Tracking expectations?**
   > "What do you want to track? Project state (which milestone, current cohort/iteration)? Quality metrics (test pass rate, performance numbers)? Budget consumption? Anything else? List the fields you'd want on a dashboard."

4. **Completion criteria?**
   > "How will you know this project is done? List 2–5 concrete signals. Be falsifiable — 'works well' doesn't count."

5. **Token budget?**
   > "What's the rough token budget over the project's lifetime? Per-cohort budget if iterative? Hard ceiling or soft target?"

For each question: ask, listen, capture, follow up if vague. Don't paraphrase the
user's answer back as if it's a refinement — capture verbatim plus ANY follow-up
questions you genuinely had.

### Step 3 — Sketch the work shape

**`team` archetype:**
> "Let's sketch milestones at a HIGH LEVEL — not a task list. 2 to 5 milestones that
> together get you to your completion criteria. Each milestone should have a
> verifiable output and an explicit human go/no-go gate. Want to draft these together?"

**`workflow` archetype:** sketch a **task list** instead (the proto-`TASKS.yaml`) — ordered
units of work, each with a verifiable output and a `depends_on`. Then sketch the **gate
vocabulary** by reading the repo's verification surface (test suites, CI, build targets,
invariants — W5: gates are codebase-derived, not a fixed list); flag any gate with **no
backing capability** as a skill to produce (e.g. a pre/post parity harness). This is a
sketch — expect it to be re-cut as implementation reveals the true shape (W7).

Co-write with the user. Push back if a unit is too vague or too granular.

### Step 4 — Identify uncertainties

> "What about this project are you genuinely uncertain about right now? What might
> we get wrong in design that we'll have to revisit?"

Capture these as open questions. They become valuable for Phase 2 (planning) and
Phase 3 (design).

### Step 5 — Write the brainstorm document

Create `docs/superpowers/<project>/<team>/brainstorms/brainstorm-<session-id>.md`:

```markdown
# <Project name> — Brainstorm <session-id>

Written <ISO-timestamp> by the lead (`<orchestrator-name>`) in conversation with
the human user.

## Goal (verbatim from user)

> <one-paragraph goal>

## Other agents needed

<user's answer>

## Verification posture

<user's answer + specifics>

## Tracking expectations

<list of fields the user wants on the dashboard>

## Completion criteria

<2–5 concrete signals>

## Token budget

<budget; mark `hard` or `soft`>

## Milestone sketch (high-level, for Phase 2 to refine)

1. <milestone-1>: <output> | go/no-go: <criterion>
2. <milestone-2>: <output> | go/no-go: <criterion>
   ...

## Open uncertainties (carry into Phase 2 + 3)

- <uncertainty-1>
- <uncertainty-2>
   ...

## Revisions

(If this is a runtime revision of a prior brainstorm, link to it and explain
the pivot.)
```

### Step 6 — Update the tracker

After writing the file, send the tracker a message:

```
plan_update:
  current_brainstorm: <relative-path-to-brainstorm-file>
```

The tracker will append a `brainstorm_revised` event and update its
`current_brainstorm` + `brainstorm_history`.

### Step 7 — Confirm with the user

Show the user the brainstorm doc path and a 2-sentence summary. Ask if they
approve to move to Phase 2 (planning).

## What this skill is NOT

- Not a generic problem-solving brainstorm. It's specifically about team-design intent.
- Not Phase 2. We don't decompose into milestones in detail here — that's Phase 2's job. We just SKETCH them.
- Not autonomous. Every section requires the user's input. Don't fabricate answers.

## Failure modes

- **User declines to answer one of the 5 interrogation questions** → record `<question-id>: declined` and proceed. Note in the doc that the field is undeclared.
- **User wants to revise mid-flight** → revise the in-progress file before saving; never partial-save and resume — the brainstorm is atomic per session.


## Output review

The review checklist for this phase lives at `references/review.md` — extracted from this skill so a separately-dispatched **review subagent** can load just the criteria without the full procedural skill body (context isolation).

**Two equivalent ways to run the review:**

1. **Inline (lighter, lead does it)** — read `references/review.md` yourself, run the checklist against the file(s) you just produced, surface ✓/✗ results to the user before the approval ask.

2. **Subagent (more isolated, fresh context)** — dispatch a subagent with the prompt:
   > "Review the output at `<path-to-output-file>` against the criteria in `references/review.md` of the team-forge `<this-skill-name>` skill. Report the checklist as a ✓/✗ list, then name any specific gaps for each ✗."
   The subagent reads only the criteria file + the output — no other team-forge context required.

Either path produces the same checklist output. The subagent path is preferable when the lead's context window is large enough that adding the review work would crowd it, or when a colder/independent verdict is wanted.

After the review (regardless of path), surface results to the user and ask: approve, revise, or abort. **Do not auto-pass on a hard-abort trigger** (those are documented in `references/review.md` per phase).
