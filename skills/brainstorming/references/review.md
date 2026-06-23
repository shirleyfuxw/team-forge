# Brainstorming output review

Evaluate a `brainstorm-<session-id>.md` from Phase 1. Loadable standalone by a review subagent.

## The checks that matter

Only two things a capable model won't get right on its own — both are team-forge convention, not general writing quality:

| # | Check | Pass condition |
|---|---|---|
| 1 | All 5 interrogation areas present | Each of "Other agents needed", "Verification posture", "Tracking expectations", "Completion criteria", "Token budget" has a real answer or an explicit `declined` line. (The *specific five* are the convention — easy to silently drop one.) |
| 2 | File at the canonical path | `docs/team-forge/<team>/brainstorms/brainstorm-<session-id>.md`, `<session-id>` an ISO date or a meaningful slug. |

Everything else (goal captured clearly, milestones sketched not over-detailed, uncertainties noted) a competent model does naturally — don't checklist it.

## Reporting

```
Brainstorm review:
- [✓/✗] All 5 interrogation areas present  (name any missing)
- [✓/✗] File at canonical path
```

## Hard-abort triggers

None. Surface gaps; the user decides revise / accept / abort.
