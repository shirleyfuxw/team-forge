# Brainstorming output review

Evaluate a `brainstorm-<session-id>.md` from Phase 1. Loadable standalone by a review subagent.

## The checks that matter

Only two things a capable model won't get right on its own — both are team-forge convention, not general writing quality:

| # | Check | Pass condition |
|---|---|---|
| 1 | All 5 interrogation areas present | Each of "Other agents needed", "Verification posture", "Tracking expectations", "Completion criteria", "Token budget" has a real answer or an explicit `declined` line. (The *specific five* are the convention — easy to silently drop one.) |
| 2 | File at the canonical path | `docs/team-forge/<team>/brainstorms/brainstorm-<session-id>.md`, `<session-id>` an ISO date or a meaningful slug. |
| 3 | Existing KB surveyed / reconciled | The doc reflects a survey of prior brainstorms + plans: it either builds on the current lineage (linked in `## Revisions`) or explicitly notes "fresh project, no prior KB", and does not silently contradict a prior decision. |

Everything else (goal captured clearly, milestones sketched not over-detailed, uncertainties noted) a competent model does naturally — don't checklist it.

## Reporting

```
Brainstorm review:
- [✓/✗] All 5 interrogation areas present  (name any missing)
- [✓/✗] File at canonical path
- [✓/✗] Existing KB surveyed / reconciled  (built on prior lineage, or "fresh project"; no silent contradiction)
```

## Hard-abort triggers

None. Surface gaps; the user decides revise / accept / abort.
