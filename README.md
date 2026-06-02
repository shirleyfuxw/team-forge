# team-forge

Meta-extension for Claude Code that auto-generates project-specific agent teams.

**Status:** MVP complete + end-to-end forge test passed (v0.0.2). See [SCOPING.md](./SCOPING.md) for full design, [tests/README.md](./tests/README.md) for what was validated.

## What it does

Forges a project-specific multi-agent team — roster, team-launcher skill, observability hub — for any project domain. Each forged team:

- Spawns persistent teammates via Claude Code's `agent-teams` primitive (experimental)
- Enforces a 5-role coverage rule: **work / verify / advise / tracker / monitor**
- Includes a runtime dashboard at `.claude/team-forge/<team>/playground/dashboard.html`
- Survives `/resume` via an explicit rehydrate protocol (tracker is load-bearing)

team-forge is the wiring; the procedural toolbox (TDD, debugging, planning, brainstorming) is provided by Superpowers and the project's own skills.

## The 4-phase loop

1. **Brainstorm** (`team-forge:brainstorming`) — agent-team-aware interrogation
2. **Plan** (`team-forge:writing-plans`) — high-level milestones with hard dependencies + interfaces
3. **Design** (`team-forge:design`) — multiple forge-design-agents produce `design.yaml` (the Phase 4 contract). Skill discovery searches `<project>/.claude/skills/` + `~/.claude/skills/` + installed plugins.
4. **Forge** (`team-forge:forge`) — emits agent `.md` files, team-launcher skill, design.yaml + manifest, initial tracker `status.json` + dashboard `dashboard.html`, KB scaffolds under `docs/superpowers/<project>/<team>/`.

## Requires

- Claude Code v2.1.32 or later
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment
- For optional deterministic forging: `python3` + `pyyaml`

## Install (local development)

```
/plugin marketplace add ~/team-forge
/plugin install team-forge@team-forge-dev
```

Then in any Claude Code session: ask Claude to "use team-forge to design an agent team for `<project>`".

## What ships in this extension

- **7 skills** (`skills/<name>/SKILL.md`):
  - `brainstorming`, `writing-plans`, `design`, `forge` — the 4 phases
  - `rehydrate` — `/resume` protocol
  - `tracker`, `monitor` — runtime role patterns
- **4 templates** (`templates/`):
  - `design.yaml.j2` — schema reference for Phase 3 (logic-free)
  - `agent.md.j2` — per-agent emission (logic-free `{{VAR}}` + placeholder blocks)
  - `team-launcher.md.j2` — `<team>-team` slash command
  - `dashboard.html.j2` — initial dashboard render
- **1 hook** (`hooks/session-start`) — slim availability announcement
- **1 optional renderer** (`tools/forge.py`) — Python script that runs the forge skill procedure deterministically against a design.yaml
- **1 test fixture** (`tests/`) — end-to-end forge test run on a throwaway "greeter" team; documents what was validated pre-v0.1

## Roadmap

- [x] v8.2 design freeze ([SCOPING.md](./SCOPING.md))
- [x] Items 1–11: repo skeleton + manifests + 7 skills + 4 templates
- [x] Advisor end-to-end review — addressed all 3 blockers + 4 medium items
- [x] First end-to-end forge test on `/tmp/test-team-forge-greeter/` (6-agent team, 10 files generated cleanly)
- [ ] v0.1: GitHub push, marketplace install path

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).
