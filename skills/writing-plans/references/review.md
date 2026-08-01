# Team-plan output review

Evaluate a Phase 2 team-plan (`<slug>-plan-<YYYY-MM-DD>.md`). Loadable standalone by a review subagent.

## The checks that matter

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | No cyclic dependencies | Topo-sort the `hard_dependencies` graph; any cycle fails. | **Yes** — plan is unbuildable |
| 2 | Dependencies + interfaces declared | Every milestone has `hard_dependencies: [...]` (empty OK), and every non-final milestone has an `interface_to_next` (2–3 sentences). | **Yes** — Phase 3 fails downstream without these |
| 3 | Per-milestone fields complete | Each milestone has `output`, `go_no_go`, `expected_team_size`, `next_phase_check`, and an iteration shape (one-shot / iterative). | No (warn) |
| 4 | Filename is meaningful + dated | The file is named `<slug>-plan-<YYYY-MM-DD>.md` — a content-descriptive slug plus the date. A generic/undated name (`team-plan-v1.md`, `team-plan.md`) fails. | No (warn — rename before approval) |
| 5 | Existing artifacts reviewed / non-duplicative | The plan builds on the current team-plan + done artifacts rather than re-planning covered work; a follow-on plan scopes to new work and cites what prior plans delivered; contradictions of prior decisions/gated results are surfaced, not silent. | No (warn) |
| 6 | Next-phase route stated + earned | `## Next-phase route` names one of `phase-3-design` / `fold-into-existing-runtime` / `direct-execution`. A fast-path route must cite its criteria (existing roster/gates for fold-in; no new assets + runnable gates + same-session for direct execution) AND have an empty Carry-overs section — unresolved carry-overs force `phase-3-design`. | No (warn — default to `phase-3-design` if unjustified) |
| 7 | Goal directive revised for add-on scope | A follow-on/add-on plan states how `status.json.goal_directive` changes (new `done_when` signals; `lead_decides`/`user_decides` deltas if the risk class changed) or explicitly "directive unchanged — same scope re-cut". Silent on the goal = fail this check. | No (warn — revise before the first new task runs) |

Skip the rest (milestones high-level, cross-milestone notes, carry-overs) — a capable model produces those without a checklist.

## Reporting

```
Team-plan review:
- [✓/✗] No cyclic dependencies              (hard abort)
- [✓/✗] Dependencies + interfaces declared  (hard abort; name gaps)
- [✓/✗] Per-milestone fields complete       (name any milestone missing a field)
- [✓/✗] Filename meaningful + dated         (warn; rename if generic/undated)
- [✓/✗] Existing artifacts reviewed         (warn; non-duplicative, contradictions surfaced)
- [✓/✗] Next-phase route stated + earned    (warn; fast path needs cited criteria + empty carry-overs)
- [✓/✗] Goal directive revised or confirmed (warn; add-on scope must update status.json.goal_directive)
```

## Hard-abort triggers

Cyclic dependencies → abort, one milestone must be re-scoped or merged.
Missing `hard_dependencies` or `interface_to_next` → blocking; revise before Phase 3.
