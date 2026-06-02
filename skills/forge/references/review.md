# Forge output review

**Purpose:** evaluate the file outputs produced by Phase 4. Designed for use either by the forge skill itself OR by a separately-dispatched review subagent that only needs the manifest + filesystem state.

## Inputs

- Path to the team's manifest.json (`<target_repo>/.claude/team-forge/<team>/manifest.json`)
- Path to the design.yaml that produced the forge
- The target_repo root (for filesystem reconciliation)

## Criteria

| # | Check | Pass condition |
|---|---|---|
| 1 | All manifest files exist on disk | For every entry in `manifest.json.generated_files`, the file at `path` exists. |
| 2 | Agent .md frontmatter valid | Every emitted `<target>/.claude/agents/*.md` from this team starts with `---` and has `name:` + `description:` + `model:` fields. |
| 3 | Agent names match expected pattern | Non-shared: filename = `<team>-<roster-name>.md`. Shared (`shared_across_teams: true`): filename = `<roster-name>.md` (no prefix). |
| 4 | Team-launcher skill exists | `<target>/.claude/skills/<team>-team/SKILL.md` was written with non-empty body and valid frontmatter (`name:` + `description:`). |
| 5 | tracker/status.json parses as JSON | File parses cleanly. Has all `tracking.state_shape` fields + `forge_metadata` block with `forged_at_iso` + `design_hash` + `forge_version`. |
| 6 | dashboard.html non-empty + has expected panels | File exists, > 1k bytes. Contains each panel ID from `design.tracking.dashboard_panels`. |
| 7 | KB scaffold complete | `<target>/docs/superpowers/<basename>/<team>/` exists with subdirs: `brainstorms/`, `team-plans/`, `artifacts/<id>/` per milestone, `runtime/<id>/` per milestone. README.md exists. |
| 8 | manifest.json design_hash matches | sha256 of design.yaml on disk equals `manifest.json.design_hash`. Mismatch means design drifted after forge. |
| 9 | No orphan agents | Any pre-existing `<target>/.claude/agents/<team>-*.md` files NOT in the manifest are flagged. |
| 10 | Roster ↔ manifest 1:1 | One `agent_md` entry in manifest per roster entry. No extras, no missing. |

## Reporting format

```
Forge output review:
- [✓ or ✗] All manifest files exist on disk (N files checked)
- [✓ or ✗] Agent .md frontmatter valid (N agents)
- [✓ or ✗] Agent names match prefix/shared rule
- [✓ or ✗] Team-launcher skill written
- [✓ or ✗] tracker/status.json parses as JSON
- [✓ or ✗] dashboard.html contains expected panels
- [✓ or ✗] KB scaffold complete
- [✓ or ✗] manifest.json design_hash matches
- [✓ or ✗] No orphan agents
- [✓ or ✗] Roster ↔ manifest 1:1
```

For each ✗: cite the specific file, frontmatter field, or roster entry that failed.

## Hard-abort triggers

- **Missing manifest files on disk**: hard abort. The forge wrote the manifest but the files aren't there — write error mid-emission. Tell user to clean partial output and re-run.
- **Invalid agent frontmatter**: hard abort. Agents won't be discoverable by Claude Code.
- **status.json doesn't parse**: hard abort. Rehydrate won't work.
- **design_hash mismatch**: warning, not abort. Tell user the design drifted after forge — they may want to regenerate.
- **Roster ↔ manifest mismatch**: hard abort. Forge procedure was interrupted; partial team won't function.
