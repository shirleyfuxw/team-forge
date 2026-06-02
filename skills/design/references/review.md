# Design output review

**Purpose:** evaluate a `design.yaml` produced by Phase 3. Designed for use either by the design skill itself OR by a separately-dispatched review subagent (e.g. as a final check after the multi-agent Phase 3 reciprocal review).

## Inputs

- Path to the design.yaml file (typically `<target_repo>/.claude/team-forge/<team>/design.yaml`)
- Optional: the team-plan + brainstorm files (for upstream cross-reference)

## Criteria

| # | Check | Pass condition |
|---|---|---|
| 1 | Schema validation | design.yaml parses as YAML. Top-level sections present: `project`, `milestones`, `roster`, `rehydrate`, `tracking`, `constraints`, `skill_discovery_results`. |
| 2 | Required project fields | `project.name`, `target_repo`, `target_repo_basename`, `display_name`, `domain`, `brief` all non-empty. |
| 3 | Role coverage | At least one teammate covers each role: work, verify, advise, tracker, monitor. Coverage via direct `role:` or via `combined_roles: [...]`. |
| 4 | Orchestrator present | Exactly one roster entry with `role: orchestrator`. Zero or multiple fail. |
| 5 | Comms closure | Every `tracking.state_shape[].source` is either `"lead"` or a name that exists in `roster`. |
| 6 | tracking.events_to_log enumerated | Non-empty list. Must include at minimum: `milestone_started`, `milestone_completed`, `rehydrate`. |
| 7 | tracking.dashboard_panels backed by data | Every panel ID either has corresponding fields in `state_shape` or is a generic panel team-forge knows how to render (`milestone_timeline`, `team_roster_and_status`, `current_pointers`, `recent_events`). |
| 8 | Skill loadouts proposed for every teammate | `skill_discovery_results.proposed_loadouts_per_teammate` has an entry per teammate. Empty list `[]` is OK for pure prompt-driven agents. |
| 9 | Constraints non-empty | At least one project-specific constraint declared. |
| 10 | Lens disagreements resolved | If the multi-agent Phase 3 review (Lens 1+2+3) flagged conflicts, every conflict is either resolved in the final design or explicitly surfaced as an open question. |

## Reporting format

```
Design review:
- [✓ or ✗] Schema parses + all sections present
- [✓ or ✗] Required project fields non-empty
- [✓ or ✗] Role coverage (all 5 roles + orchestrator)
- [✓ or ✗] Comms closure (all sources resolve)
- [✓ or ✗] tracking.events_to_log enumerated
- [✓ or ✗] tracking.dashboard_panels backed by data
- [✓ or ✗] Skill loadouts proposed per teammate
- [✓ or ✗] Constraints non-empty
- [✓ or ✗] Lens disagreements resolved
```

For each ✗: cite the specific field or roster entry.

## Hard-abort triggers

- **Schema doesn't parse**: hard abort. Phase 4 cannot read the design.
- **Role coverage failure**: hard abort. Re-dispatch the Phase 3 design agents with the missing role as required.
- **Comms closure failure**: hard abort. Either add the missing roster entry or change the source.

Soft warnings (proceed with user notification): events_to_log gaps, missing constraints, unresolved Lens disagreements.
