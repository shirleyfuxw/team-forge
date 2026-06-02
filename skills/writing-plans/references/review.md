# Team-plan output review

**Purpose:** evaluate a `team-plan-v<n>.md` file produced by Phase 2. Designed for use either by the writing-plans skill itself OR by a separately-dispatched review subagent.

## Inputs

- Path to the team-plan markdown file
- The current brainstorm file (for carry-over validation)

## Criteria

| # | Check | Pass condition |
|---|---|---|
| 1 | All milestones high-level | No detail sub-tasks; each milestone is a verifiable unit with a go/no-go gate. |
| 2 | Hard dependencies declared | Every milestone has `hard_dependencies: [...]` (empty list OK; missing field fails). |
| 3 | No cyclic dependencies | Topo sort on the dependency graph; cycles fail. |
| 4 | Interface_to_next described | Every milestone (except last) has 2–3 sentences describing its handoff. |
| 5 | Iteration shape per milestone | Each marked `one-shot` or `iterative` (iterative includes rough iteration count). |
| 6 | Expected team size declared | Each milestone has an integer team-size estimate. |
| 7 | Next-phase check declared | Each milestone has a human go/no-go criterion at the next-milestone gate. |
| 8 | Cross-milestone notes present | Section on parallel-runnable milestones + critical path + token budget allocation. |
| 9 | Brainstorm carry-overs tracked | Any brainstorm uncertainties not resolved here are explicitly listed. |

## Reporting format

```
Team-plan review:
- [✓ or ✗] All milestones high-level
- [✓ or ✗] Hard dependencies declared
- [✓ or ✗] No cyclic dependencies
- [✓ or ✗] Interface_to_next described for each milestone
- [✓ or ✗] Iteration shape per milestone
- [✓ or ✗] Expected team size declared
- [✓ or ✗] Next-phase check declared
- [✓ or ✗] Cross-milestone notes section present
- [✓ or ✗] Brainstorm carry-overs tracked
```

For each ✗: name the specific milestone or section that's missing the field.

## Hard-abort triggers

- **Cyclic dependencies**: automatic abort. The plan is unbuildable until one milestone is re-scoped or merged.
- **Missing hard_dependencies or interface_to_next**: blocking — Phase 3 will fail downstream. Treat as hard ✗ and ask user to revise before proceeding.
