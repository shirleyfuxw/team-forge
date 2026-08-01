# Contract output review

Evaluate a `docs/team-forge/<team>/contract.yaml`. Loadable standalone by a review
subagent. The mechanical bar is `tools/contract_lint.py` — run it first; this
checklist covers only what the lint can't judge.

## The checks that matter

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | Lint green | `python3 <ext>/tools/contract_lint.py <contract>` exits 0. | **Yes** — the deliverable's definition |
| 2 | Problem, not ask | `problem.statement` names the problem behind the user's phrasing (what breaks, for whom); a task list or a pre-chosen fix restated as the problem fails. | No (warn) |
| 3 | Checks are real, not decorative | Spot-run (or dry-read) each `done_when[].check` against the repo: named commands/gates/files must exist or be produced by the plan. A check referencing nothing that exists or is planned fails. | **Yes** — fake checks are worse than none |
| 4 | open_items honest | Conditions discussed with the user but not in `done_when` appear in `open_items` with what's missing — not silently dropped. | No (warn) |
| 5 | Route earned | `route: machinery` cites at least one earned criterion (uncheckable-without-new-capability / cross-session-or-unattended / genuine fan-out). `direct-execution` with open_items that block it fails. | No (warn — default direct-execution) |
| 6 | Task sketch sound (when present) | `tasks` DAG acyclic; every task has a verifiable `output`. | **Yes** on a cycle |
| 7 | KB reconciled | Revision of the existing contract lineage (not a parallel one); contradictions with prior decisions/gated results surfaced, not silent; live `goal_directive` synced or explicitly "unchanged". | No (warn) |
| 8 | Scope figures labeled | Counts are verified (command cited) or labeled estimates; no unclosed headline number. | No (warn) |

## Reporting

```
Contract review:
- [✓/✗] Lint green                    (hard abort)
- [✓/✗] Problem, not ask
- [✓/✗] Checks are real               (hard abort; name any phantom check)
- [✓/✗] open_items honest
- [✓/✗] Route earned
- [✓/✗] Task sketch sound             (hard abort on cycle; n/a if no tasks)
- [✓/✗] KB reconciled / directive synced
- [✓/✗] Scope figures labeled
```

## Hard-abort triggers

Lint failure · a `check` that references nothing existing or planned · a cyclic
task sketch. Everything else: surface; the user decides revise / accept / abort.
