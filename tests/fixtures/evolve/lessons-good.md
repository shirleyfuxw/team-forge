# drain — lessons register

> Verified against team-forge **0.12.0** · last evolve 2026-09-01 (cycle-2026-09-01-001) · events mined: 26
> One version governs this file. Admission: a row needs evidence (recurrence >= 2,
> blocked->resolved, gate failure with root cause, budget attribution). Single anecdotes
> go to ## Candidates.

Fixture: a VALID register, for `evolve_mine.py --lint-register`. Its sibling lessons-bad.md
carries one seeded defect per lint rule.

## Active

| # | Lesson | Evidence | Applied to (layer:path) | Check | Since |
|---|---|---|---|---|---|
| LL-1 | Build the verify brief from the diff, never from the lead's summary | recurrence x3 (`verifier_prompt_contamination`, cycle-2026-09-01-001) | L2:design.yaml#worker.procedure | `grep -c 'from the diff' .claude/agents/drain-worker.md` returns >= 1 | 2026-09-01 |
| LL-2 | Worker scratch files live outside the repo root | blocked->resolved (#1885, branch-safety hook) | L1:.claude/agent-memory/drain-lead/MEMORY.md | dispatch brief names /tmp as the scratch root | 2026-09-01 |

## Superseded / falsified

| # | Lesson | Died at | Replaced by |
|---|---|---|---|
| LL-0 | The review gate can dispatch the code-review agent | cycle-2026-09-01-001: workflow agents have no Agent tool, so the gate was unsatisfiable as written | LL-3 |

## Candidates (evidence pending)

| C-id | Claim | Seen | First/last |
|---|---|---|---|
| C-1 | Waves of three drain faster than waves of four on this repo | 1 | 2026-09-01 / 2026-09-01 |

## Unexercised (ablation queue)

| What | Since | Runs without a trace | Decision |
|---|---|---|---|
| gate `leak_guard` | 2026-08-25 | 1 | keep one more cycle |
