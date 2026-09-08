# drain — lessons register

> Verified against team-forge **0.12.0** · last evolve 2026-09-01 (cycle-2026-09-01-001) · events mined: 26
> One version governs this file. Admission: a row needs evidence (recurrence >= 2,
> blocked->resolved, gate failure with root cause, budget attribution). Single anecdotes
> go to ## Candidates.

Fixture: FOUR seeded defects, one per STRUCTURAL lint rule in `evolve_mine.py
--lint-register` — the rules that judge the register's shape rather than a single row's
cells. Its sibling lessons-bad.md seeds the four row-level rules. Kept apart because the
structural rules were added later and each needs a control of its own: a rule that has
never been watched go red on a file that violates it is a comment with an if-statement
around it.

DEFECT 1: the paragraph below line-wraps onto a `## Candidates` line. This is the real
defect the forge shipped — templates/lessons.md.j2 wrapped exactly this sentence, so every
forged register carried a phantom Candidates heading mid-prose and still linted clean.
Anecdotes go to
## Candidates and wait for a second sighting — they are not deleted, and they are not applied.

## Active

| # | Lesson | Evidence | Applied to (layer:path) | Check | Since |
|---|---|---|---|---|---|
| LL-1 | Build the verify brief from the diff, never from the lead's summary | recurrence x3 (`verifier_prompt_contamination`) | | `grep -c 'from the diff' .claude/agents/drain-worker.md` returns >= 1 | 2026-09-01 |
| LL-2 | Build the verify brief from the diff and never from the lead's summary | recurrence x2 (cycle-2026-09-01-001) | L2:design.yaml#worker.procedure | `grep -c 'from the diff' .claude/agents/drain-worker.md` returns >= 1 | 2026-09-01 |

DEFECT 2 is LL-1's empty "Applied to" cell: a lesson naming no layer:path was never applied
to anything, so nothing about the repo changed and the row is a Candidate wearing a lesson's
clothes. DEFECT 3 is LL-2 restating LL-1 — one lesson carried twice is two registers, and
they start disagreeing at the first supersede.

## Superseded / falsified

| # | Lesson | Died at | Replaced by |
|---|---|---|---|
| LL-0 | The review gate can dispatch the code-review agent | cycle-2026-09-01-001: workflow agents have no Agent tool | LL-3 |

## Candidates (evidence pending)

| C-id | Claim | Seen | First/last |
|---|---|---|---|
| C-1 | Waves of three drain faster than waves of four on this repo | 1 | 2026-09-01 / 2026-09-01 |

DEFECT 4: the "## Unexercised (ablation queue)" section is missing entirely. An absent table
and an empty one read identically to a row-only linter — every ablation rule then iterates
over nothing and reports green, which is how the prune half of the doctrine quietly stops
happening.
