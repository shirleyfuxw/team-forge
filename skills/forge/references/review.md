# Forge output review

Evaluate Phase 4 output. Loadable standalone by a review subagent: needs only the manifest, the design.yaml, and the target_repo root. This is filesystem reconciliation — the one review that's genuinely mechanical (a half-failed emission leaves real broken state), so it's the densest of the four on purpose.

## The checks that matter

| # | Check | Pass condition | Hard abort? |
|---|---|---|---|
| 1 | Manifest ↔ filesystem | Every path in `manifest.json.generated_files` exists on disk. | **Yes** — partial emission |
| 2 | Roster ↔ manifest 1:1 | One `agent_md` manifest entry per roster entry; no extras, none missing. | **Yes** |
| 3 | Agent frontmatter valid | Every emitted `agents/*.md` opens with `---` and has `name:` + `description:` + `model:`. | **Yes** — else undiscoverable |
| 4 | tracker/status.json parses | Valid JSON; has the `tracking.state_shape` fields + `forge_metadata`. | **Yes** — else rehydrate breaks |
| 5 | design_hash matches | sha256 of design.yaml == `manifest.json.design_hash`. | No (warn — design drifted post-forge) |

Skip the fine-grained ones (exact prefix on each name, dashboard byte-count, KB subdir-by-subdir) — if checks 1+2 pass, those are almost certainly fine, and `forge.py` already self-checks during emission.

## Reporting

```
Forge output review:
- [✓/✗] Manifest ↔ filesystem (N files)     (hard abort)
- [✓/✗] Roster ↔ manifest 1:1               (hard abort)
- [✓/✗] Agent frontmatter valid (N agents)  (hard abort)
- [✓/✗] tracker/status.json parses          (hard abort)
- [✓/✗] design_hash matches                 (warn only)
```

## Hard-abort triggers

Any ✗ on checks 1–4 → do NOT report success. Tell the user what emitted vs failed; recommend deleting the partial output and re-running `forge.py`.
