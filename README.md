# team-forge

Meta-extension for Claude Code that auto-generates project-specific agent teams.

**Status:** MVP scaffolded (v0.0.1). See [SCOPING.md](./SCOPING.md) for full design + roadmap.

## What it does

Forges a project-specific multi-agent team — roster, team-launcher skill, observability hub — for any project domain (combiner research, frontend builds, ML pipelines, backend APIs, data pipelines, custom). Each forged team:

- Spawns persistent teammates via Claude Code's `agent-teams` primitive (experimental)
- Enforces a 5-role coverage rule: **work / verify / advise / tracker / monitor**
- Includes a runtime dashboard at `docs/superpowers/<project>/<team>/`
- Survives `/resume` via an explicit rehydrate protocol (tracker is load-bearing)

team-forge is the wiring; the procedural toolbox (TDD, debugging, planning, brainstorming) is provided by Superpowers and the project's own skills. Forged teammates reference both.

## The 4-phase loop

team-forge runs a human-in-the-loop design loop ending with concrete files committed to the target project:

1. **Brainstorm** — agent-team-aware interrogation. What's the goal? What other agents? What verification? What tracking? Budget?
2. **Plan** — high-level milestones with hard dependencies, interfaces between milestones, expected team size.
3. **Design** — multiple forge-design-agents in parallel produce an annotated `design.yaml` (the Phase 4 contract). Skill discovery happens here: forge searches `<project>/.claude/skills/`, `~/.claude/skills/`, and installed plugins to propose per-teammate loadouts.
4. **Forge** — emits agent `.md` files, team-launcher skill, design.yaml + manifest, initial tracker `status.json` + dashboard `dashboard.html`, and KB scaffolds under `docs/superpowers/<project>/<team>/`.

## Requires

- Claude Code v2.1.32 or later
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment

## Install (local development)

```
/plugin marketplace add ~/team-forge
/plugin install team-forge@team-forge-dev
```

Then in any Claude Code session: ask Claude to "use team-forge to design an agent team for `<project>`".

## What ships in this extension

- **7 skills** (`skills/`):
  - `team-forge-brainstorming` — Phase 1 (active interrogation)
  - `team-forge-writing-plans` — Phase 2 (milestone planning with hard-dependency interrogation)
  - `team-forge-design` — Phase 3 (multi-agent design with reciprocal review)
  - `team-forge-forge` — Phase 4 (deterministic file emission)
  - `team-forge-rehydrate` — `/resume` protocol
  - `team-forge-tracker` — tracker-role generic pattern
  - `team-forge-monitor` — monitor-role generic pattern
- **4 templates** (`templates/`):
  - `design.yaml.j2` — Phase 3 schema (the contract)
  - `agent.md.j2` — per-agent emission
  - `team-launcher.md.j2` — `<team>-team` slash command
  - `dashboard.html.j2` — initial dashboard render
- **1 hook** (`hooks/session-start`) — slim availability announcement

## Roadmap

- [x] v8.2 design freeze ([SCOPING.md](./SCOPING.md))
- [x] Item 1: repo skeleton + manifests
- [x] Item 2: `templates/design.yaml.j2`
- [x] Item 3: `templates/agent.md.j2` + `templates/team-launcher.md.j2`
- [x] Item 4: `skills/team-forge-forge/SKILL.md` (Phase 4 logic)
- [x] Item 5: `skills/team-forge-rehydrate/SKILL.md` (runtime `/resume` protocol)
- [x] Item 6: `skills/team-forge-tracker/SKILL.md`
- [x] Item 7: `skills/team-forge-monitor/SKILL.md`
- [x] Item 8: `templates/dashboard.html.j2`
- [x] Item 9: `skills/team-forge-design/SKILL.md`
- [x] Item 10: `skills/team-forge-brainstorming/SKILL.md`
- [x] Item 11: `skills/team-forge-writing-plans/SKILL.md`
- [ ] First end-to-end forge test on a small generic project (validate Phase 1 → 4 on real input)
- [ ] v0.1: GitHub push, marketplace install path

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE) (Superpowers + agent-teams + HERC prior-art attribution).
