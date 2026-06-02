# Team-plan output review

Evaluate a `team-plan-v<n>.md` from Phase 2. Loadable standalone by a review subagent.

## The checks that matter

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | No cyclic dependencies | Topo-sort the `hard_dependencies` graph; any cycle fails. | **Yes** — plan is unbuildable |
| 2 | Dependencies + interfaces declared | Every milestone has `hard_dependencies: [...]` (empty OK), and every non-final milestone has an `interface_to_next` (2–3 sentences). | **Yes** — Phase 3 fails downstream without these |
| 3 | Per-milestone fields complete | Each milestone has `output`, `go_no_go`, `expected_team_size`, `next_phase_check`, and an iteration shape (one-shot / iterative). | No (warn) |

Skip the rest (milestones high-level, cross-milestone notes, carry-overs) — a capable model produces those without a checklist.

## Reporting

```
Team-plan review:
- [✓/✗] No cyclic dependencies              (hard abort)
- [✓/✗] Dependencies + interfaces declared  (hard abort; name gaps)
- [✓/✗] Per-milestone fields complete       (name any milestone missing a field)
```

## Hard-abort triggers

Cyclic dependencies → abort, one milestone must be re-scoped or merged.
Missing `hard_dependencies` or `interface_to_next` → blocking; revise before Phase 3.
