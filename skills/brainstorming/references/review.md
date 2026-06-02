# Brainstorming output review

**Purpose:** evaluate a `brainstorm-<session-id>.md` file produced by Phase 1. Designed for use either by the brainstorming skill itself OR by a separately-dispatched review subagent that only needs the criteria.

## Inputs

- Path to the brainstorm markdown file
- Optional: the user's original goal statement (for verbatim-capture check)

## Criteria

| # | Check | Pass condition |
|---|---|---|
| 1 | Goal captured verbatim | The user's one-paragraph goal appears in the doc word-for-word. Paraphrasing fails. |
| 2 | All 5 interrogation areas covered | Each of "Other agents needed", "Verification posture", "Tracking expectations", "Completion criteria", "Token budget" has either a real answer or an explicit `<question-id>: declined` line. |
| 3 | Milestones sketched (not detailed) | Section contains 2–5 high-level milestones with verifiable outputs + go/no-go gates. Sub-task lists fail. |
| 4 | Uncertainties captured | At least one open question listed, OR an explicit "no uncertainties surfaced" note. |
| 5 | File path correct | The file lives at `docs/superpowers/<project>/<team>/brainstorms/brainstorm-<session-id>.md` where `<session-id>` is an ISO date or a meaningful slug (e.g. `phase1-initial`, `pivot-1`). |

## Reporting format

```
Brainstorm review:
- [✓ or ✗] Goal captured verbatim
- [✓ or ✗] All 5 interrogation areas covered
- [✓ or ✗] Milestones sketched (not detailed)
- [✓ or ✗] Uncertainties captured
- [✓ or ✗] File path correct
```

For each ✗: name the specific gap (which section is missing, which question wasn't answered).

## Hard-abort triggers

None. Brainstorming review surfaces gaps but does not block — the user decides whether to revise, accept-with-gaps, or abort.
