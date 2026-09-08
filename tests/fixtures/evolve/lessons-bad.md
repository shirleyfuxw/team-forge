# drain — lessons register

Fixture: the same register as lessons-good.md with FOUR seeded defects, one per lint rule
in `evolve_mine.py --lint-register`. Kept side by side with the good file on purpose — a
linter exercised only against valid input has never been shown to reject anything.

DEFECT 4: the version banner is gone. Without it a reader cannot tell a belief that was
checked against 0.12.0 from one that has not been checked since 0.9.

## Active

| # | Lesson | Evidence | Applied to (layer:path) | Check | Since |
|---|---|---|---|---|---|
| LL-1 | Build the verify brief from the diff, never from the lead's summary | recurrence x3 (`verifier_prompt_contamination`, cycle-2026-09-01-001) | L2:design.yaml#worker.procedure | `grep -c 'from the diff' .claude/agents/drain-worker.md` returns >= 1 | 2026-09-01 |
| LL-2 | Worker scratch files live outside the repo root | blocked->resolved (#1885, branch-safety hook) | L1:.claude/agent-memory/drain-lead/MEMORY.md |  | 2026-09-01 |
| LL-1 | Waves of three beat waves of four | recurrence x2 (cycle-2026-08-25-001, cycle-2026-09-01-001) | L2:design.yaml#queue.wave_size | `grep 'wave_size: 3' design.yaml` | 2026-09-01 |

DEFECT 1 is the second `LL-1` above: a reused id makes every citation of LL-1 ambiguous
forever. DEFECT 2 is LL-2's empty Check cell — an unverifiable lesson.

## Superseded / falsified

| # | Lesson | Died at | Replaced by |
|---|---|---|---|
| LL-0 | The review gate can dispatch the code-review agent |  | LL-3 |

DEFECT 3 is LL-0's empty "Died at": the claim is marked dead with no record of what killed
it, so the next reader re-derives it from the same plausible reasoning.

## Candidates (evidence pending)

| C-id | Claim | Seen | First/last |
|---|---|---|---|
| C-1 | Waves of three drain faster than waves of four on this repo | 1 | 2026-09-01 / 2026-09-01 |

## Unexercised (ablation queue)

| What | Since | Runs without a trace | Decision |
|---|---|---|---|
| gate `leak_guard` | 2026-08-25 | 1 | keep one more cycle |
