# Design output review

Evaluate a `design.yaml` from Phase 3. Loadable standalone by a review subagent. These three are exactly the hard-abort triggers — Phase 4 (`forge.py`) re-checks them and refuses to emit on failure, so catching them here saves a round-trip.

## The checks that matter

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | Schema valid + project fields | Parses as YAML; sections present (`project`, `milestones`, `roster`, `rehydrate`, `tracking`, `constraints`, `asset_discovery`); `project.{name,target_repo,target_repo_basename,display_name,domain,brief}` non-empty. | **Yes** |
| 2 | Role coverage | At least one teammate per role (work/verify/advise/tracker/monitor, via `role` or `combined_roles`) AND exactly one `orchestrator`. | **Yes** — the brand rule |
| 3 | Comms closure | Every `tracking.state_shape[].source` is `"lead"` or a name in `roster`. | **Yes** |

Soft (note but don't block): `events_to_log` includes the universal kinds; `dashboard_panels` are backed by state or generic; per-teammate loadouts present (`[]` OK); constraints non-empty; **reuse/adapt considered** — any roster entry that reinvents an available shared or reference-library (e.g. ECC) asset is flagged. A capable model gets these right most of the time; flag only if obviously off.

## Workflow archetype (`archetype: workflow`)

Different contract — the role/comms checks don't apply. Checks:

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | Schema + project fields | Parses; `archetype: workflow`; `shape ∈ {sequential-gated, parallel-drain}`; sections present (`project`, `gates`, `worker`, `ledger`, + `tasks` OR `queue`); project fields non-empty. | **Yes** |
| 2 | Task/gate integrity | sequential-gated: task DAG **acyclic**, unique ids, every `gate_set ⊆ gates`, `dispatch ∈ {inline,worker}`. parallel-drain: a `queue` block present. | **Yes** — forge.py re-checks |
| 3 | Ledger shape | `ledger.state_shape` declares `current_plan`/`plan_history` as **fields** (not literal paths); every `dashboard_panels` entry backed by state or a known panel. | **Yes** |

Soft: the gate vocabulary cites the codebase's verification surface (not invented); skill gaps are listed for any gate lacking a backing capability; `recurring` present iff scheduled.

## Reporting

```
Design review:
- [✓/✗] Schema valid + project fields non-empty   (hard abort)
- [✓/✗] Role coverage (5 roles + 1 orchestrator)   (hard abort)
- [✓/✗] Comms closure (sources resolve)            (hard abort)
- soft notes: <anything off in events/panels/loadouts/constraints; any reinvented-instead-of-reused asset>
```

## Hard-abort triggers

Any ✗ on schema, role coverage, or comms closure → re-dispatch the Phase 3 design agents with the gap as a required fix. Do not pass to Phase 4.
