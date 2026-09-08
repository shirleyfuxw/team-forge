# drain-worker memory

Native per-agent memory, in the shape Claude Code auto-manages it: one `##` section per
cycle, `###` subsections, bullets. Fixture for the miner's memory rule — the same note
carried into a SECOND cycle section is evidence; a note written once is not.

## Cycle-2026-08-25-001 — COMPLETED

### Operational learnings
- Keep verifier scratch files outside the repo root; the branch-safety hook rejects Write anywhere under it.
- The mutation-kill instrument refuses on any untracked file in the worktree, so stage before qualifying.

### Instrument cache
| what | value |
|---|---|
| pytest | 7.4.4 |
| head | 9c1f0aa21 |

## Cycle-2026-09-01-001 — COMPLETED

### Operational learnings
- Keep verifier scratch files outside the repo root; the branch-safety hook rejects Write anywhere under it.
- Waves of four saturate the machine on this repo; three finished sooner than four did.
