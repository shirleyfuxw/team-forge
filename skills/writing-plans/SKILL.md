---
name: team-forge:writing-plans
description: |
  Use when starting Phase 2 of the team-forge loop (after brainstorming produces
  a brief), OR when the lead needs to revise the team-plan because the project
  pivoted. Agent-team-aware planning with active interrogation about hard
  dependencies, interfaces between milestones, and per-milestone expected team
  size. Writes a team-plan-v<n>.md to the KB.
---

# team-forge:writing-plans — Phase 2 (or runtime plan revision)

The agent-team-aware variant of writing-plans. It produces a project-level plan
that names milestones with their hard dependencies + interfaces + expected team
sizes — NOT a detailed task list (the shared task list handles that at runtime).

## When to use

- **Phase 2 of a fresh team-forge run** — right after brainstorming
- **Runtime, mid-project** — when the scope shifts significantly enough that the
  current team-plan no longer maps to reality

## Inputs

- The brainstorm document (the latest `brainstorms/brainstorm-<session-id>.md`)
- The user (interactive)
- If runtime: the current `team-plans/team-plan-v<latest>.md` to revise from

## What you produce

A markdown file at `docs/superpowers/<project>/<team>/team-plans/team-plan-v<n>.md`
where `<n>` increments from the last team-plan (e.g., `team-plan-v1.md` on first
write, `team-plan-v2.md` on the next revision).

## Procedure

### Step 1 — Re-read the brainstorm

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

Create `docs/superpowers/<project>/<team>/team-plans/team-plan-v<n>.md`:

```markdown
# <Project name> — Team Plan v<n>

Written <ISO-timestamp> by the lead (`<orchestrator-name>`). Derived from
`brainstorms/brainstorm-<session-id>.md`.

## Project recap (1 paragraph)

<re-state the goal from the brainstorm, for grounding>

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

(If this is v2+, list what changed since v<n-1> and why.)
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
- **User wants to skip ahead to Phase 3 without naming dependencies** → tell them dependencies are mandatory; offer to mark all as `[]` only if they explicitly say so
