# Brainstorming output review

Evaluate a Phase 1 brainstorm (`<slug>-brainstorm-<YYYY-MM-DD>.md`). Loadable standalone by a review subagent.

## The checks that matter

Only two things a capable model won't get right on its own — both are team-forge convention, not general writing quality:

| # | Check | Pass condition |
|---|---|---|
| 1 | All 6 interrogation areas present | Each of "Other agents needed", "Verification posture", "Tracking expectations", "Completion criteria", "Token budget", "Autonomy contract" has a real answer or an explicit `declined` line. (The *specific six* are the convention — easy to silently drop one.) |
| 2 | Filename is meaningful + dated | `docs/team-forge/<team>/brainstorms/<slug>-brainstorm-<YYYY-MM-DD>.md` — a content-descriptive slug plus the date it was cut. Opaque/undated names (session ids, `brainstorm-v1.md`) fail — rename before approval. Which brainstorm is *current* is the tracker's job, not the filename's. |
| 3 | Existing KB surveyed / reconciled | The doc reflects a survey of prior brainstorms + plans: it either builds on the current lineage (linked in `## Revisions`) or explicitly notes "fresh project, no prior KB", and does not silently contradict a prior decision. |

Everything else (goal captured clearly, milestones sketched not over-detailed, uncertainties noted) a competent model does naturally — don't checklist it.

## Reporting

```
Brainstorm review:
- [✓/✗] All 6 interrogation areas present  (name any missing)
- [✓/✗] Filename meaningful + dated        (canonical path; no session ids / version counters)
- [✓/✗] Existing KB surveyed / reconciled  (built on prior lineage, or "fresh project"; no silent contradiction)
```

## Hard-abort triggers

None. Surface gaps; the user decides revise / accept / abort.
