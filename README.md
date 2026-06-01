# team-forge

Meta-extension for Claude Code that auto-generates project-specific agent teams.

**Status:** Pre-MVP (v0.0.1). See [SCOPING.md](./SCOPING.md) for full design + roadmap.

## What it does

Forges a project-specific multi-agent team — roster, team-launcher skill, observability hub — for any project domain (combiner research, frontend builds, ML pipelines, backend APIs, data pipelines, custom). Each forged team:

- Spawns persistent teammates via Claude Code's `agent-teams` primitive (experimental)
- Enforces a 5-role coverage rule: **work / verify / advise / tracker / monitor**
- Includes a runtime dashboard at `docs/superpowers/<project>/<team>/`
- Survives `/resume` via an explicit rehydrate protocol (tracker is load-bearing)

team-forge is the wiring; the procedural toolbox (TDD, debugging, planning, brainstorming) is provided by Superpowers and the project's own skills. The forged teammates reference both.

## The 4-phase loop

team-forge runs a human-in-the-loop design loop ending with concrete files committed to the target project:

1. **Brainstorm** — agent-team-aware interrogation. What's the goal? What other agents? What verification? What tracking? Budget?
2. **Plan** — high-level milestones with hard dependencies, interfaces between milestones, expected team size.
3. **Design** — multiple forge-design-agents in parallel produce an annotated `design.yaml` (the Phase 4 contract). Skill discovery happens here: forge searches `<project>/.claude/skills/`, `~/.claude/skills/`, and installed plugins to propose per-teammate loadouts.
4. **Forge** — emits agent `.md` files, team-launcher skill, design.yaml + manifest, initial tracker `status.json` + dashboard `dashboard.html`, and KB scaffolds under `docs/superpowers/<project>/<team>/`.

## Requires

- Claude Code v2.1.32 or later
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment

## Install

(TODO — once MVP forges HERC end-to-end. For now: developer install from local path.)

## Roadmap

- [x] v8.2 design freeze ([SCOPING.md](./SCOPING.md))
- [x] Item 1: repo skeleton + manifests
- [x] Item 2: `templates/design.yaml.j2`
- [ ] Item 3: `templates/agent.md.j2` + `templates/team-launcher.md.j2`
- [ ] Item 4: `skills/team-forge-forge/SKILL.md` (Phase 4 logic — consumes design.yaml + emits files)
- [ ] Item 5: `skills/team-forge-rehydrate/SKILL.md` (runtime `/resume` protocol)
- [ ] Items 6–8: tracker + monitor + dashboard.html.j2
- [ ] Items 9–11: design + brainstorming + writing-plans skills (upstream phases)
- [ ] First end-to-end forge test on a small generic project
- [ ] v0.1: GitHub push, marketplace install path

## License

MIT — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE) (Superpowers attribution).
