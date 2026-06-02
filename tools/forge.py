#!/usr/bin/env python3
"""End-to-end test of the team-forge MVP procedure.
Reads design.yaml + templates, renders all output files per the forge skill spec.
"""
import os, sys, json, hashlib, datetime, re, shutil
from pathlib import Path

# Try yaml; if not available, fall back to a minimal parser hint
try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip3 install pyyaml")
    sys.exit(1)

EXT_DIR = Path("/Users/shirleyfu/team-forge")
TEMPLATES_DIR = EXT_DIR / "templates"
# design.yaml path: first CLI arg, else the test fixture
_DEFAULT_DESIGN = "/tmp/test-team-forge-greeter/.claude/team-forge/greeter/design.yaml"
DESIGN_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_DESIGN)
if not DESIGN_PATH.exists():
    print(f"ERROR: design.yaml not found at {DESIGN_PATH}")
    print("Usage: python3 forge.py <path-to-design.yaml>")
    sys.exit(1)
_NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ───────── Per-role text banks (mirrors forge SKILL.md) ─────────

ROLE_DESCRIPTIONS = {
    'work': "You produce primary milestone output. Receive task assignments from the lead via the shared task list at `~/.claude/tasks/{team}/`. Hand work off to verify-role teammates before propagation. Use the mailbox (`SendMessage`) to coordinate with peers.",
    'verify': "You check outputs before they propagate. Read work-role outputs, validate against the milestone's go/no-go criteria, post verdicts to the lead via `SendMessage`, and report status updates to the team's tracker.",
    'advise': "You unblock work agents on hard problems. You are called on-demand via `Agent()` dispatch. Read shared project memory + the team's KB + the rejected-hypotheses corpus (if domain has one). Return structured advice; do not modify durable files.",
    'tracker': "You aggregate project state per the team's `tracking.state_shape` spec from design.yaml. **You are the single-writer for `.claude/team-forge/{team}/tracker/status.json`.** Read verdicts from verify-role teammates and plan outputs from the lead. Append events from `tracking.events_to_log`. Tracker is load-bearing for `/resume` — your status.json is the durable state source. Spawned FIRST on rehydrate.",
    'monitor': "You read the tracker's status.json + the narrative artifacts under `docs/superpowers/<project>/{team}/`. **You are the single-writer for `.claude/team-forge/{team}/playground/dashboard.html`.** Rewrite the dashboard per `tracking.dashboard_panels`. Trigger on every meaningful state change.",
    'orchestrator': "You are the team lead. The main session adopts this role at `/{team}-team`. You manage the shared task list, dispatch teammates, arbitrate verifier verdicts, write the team's narrative artifacts (brainstorm, plans, conclusions), and make milestone go/no-go decisions with the user. **You are the single-writer for `docs/superpowers/<project>/{team}/` narrative state.**",
}
MEMORY_AUTHORITY = {
    'tracker': "You write only to `.claude/team-forge/{team}/tracker/status.json`.",
    'monitor': "You write only to `.claude/team-forge/{team}/playground/dashboard.html` and `dashboard-data.json`.",
    'orchestrator': "You write to `docs/superpowers/<project>/{team}/{{brainstorms,team-plans,artifacts,runtime}}/`.",
    'work': "You write to ephemeral worktrees only. No durable writes.",
    'verify': "You write to ephemeral worktrees only. No durable writes.",
    'advise': "You write to ephemeral worktrees only. No durable writes.",
}

# ───────── Helpers ─────────

def substitute_simple(text, vars):
    """Replace {{var}} with vars[var]."""
    for k, v in vars.items():
        text = text.replace('{{' + k + '}}', str(v))
    return text

def render_agent_md(entry, team, project_basename):
    """Render templates/agent.md.j2 for one roster entry."""
    name = entry['name']
    shared = entry.get('shared_across_teams', False)
    agent_name = name if shared else f"{team}-{name}"
    role = entry['role']
    skills = entry.get('skills', [])

    role_block = ROLE_DESCRIPTIONS[role].format(team=team)
    skills_block = "\n".join(f"- `{s}`" for s in skills) if skills else "*None — you work from prompt context alone. Intentional for pure prompt-driven agents.*"
    memory_block = MEMORY_AUTHORITY[role].format(team=team)
    shared_block = (
        "## Shared-agent note\n\n"
        "You are `shared_across_teams: true`. Forged into the target project's `.claude/agents/` once and reused unmodified by sibling teams. Do not assume team-specific context — behavior must hold across every team that spawns you."
    ) if shared else ""

    tmpl = (TEMPLATES_DIR / "agent.md.j2").read_text()
    return substitute_simple(tmpl, {
        'agent_name': agent_name,
        'purpose': entry['purpose'].rstrip(),
        'model': entry.get('model', 'sonnet'),
        'role': role,
        'team': team,
        'project_basename': project_basename,
        'ROLE_DESCRIPTION_BLOCK': role_block,
        'SKILLS_LIST_BLOCK': skills_block,
        'MEMORY_AUTHORITY_BLOCK': memory_block,
        'SHARED_AGENT_NOTE_BLOCK': shared_block,
    }), agent_name + ".md"

def render_team_launcher(design):
    tmpl = (TEMPLATES_DIR / "team-launcher.md.j2").read_text()
    project = design['project']
    orchestrator = next((e for e in design['roster'] if e['role'] == 'orchestrator'), None)
    if not orchestrator:
        raise ValueError("No orchestrator in roster")
    team = project['name']
    orch_name = orchestrator['name'] if orchestrator.get('shared_across_teams') else f"{team}-{orchestrator['name']}"
    constraints_block = "\n".join(f"- {c}" for c in design.get('constraints', []))
    return substitute_simple(tmpl, {
        'team': team,
        'project_display_name': project['display_name'],
        'project_name': project['name'],
        'project_basename': project['target_repo_basename'],
        'target_repo': project['target_repo'],
        'domain': project['domain'],
        'orchestrator_name': orch_name,
        'CONSTRAINTS_BULLET_LIST': constraints_block,
    })

def initial_status_json(design):
    state = {}
    for s in design['tracking']['state_shape']:
        t = s['type']
        state[s['id']] = {'string':None,'int':0,'float':0.0,'bool':False,'list':[],'object':{}}[t]
    state.update({
        'current_brainstorm': None,
        'current_team_plan': None,
        'brainstorm_history': [],
        'team_plan_history': [],
        'events': [],
        'forge_metadata': {
            'forged_at_iso': _NOW,
            'design_hash': hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
            'forge_version': '0.0.1',
        }
    })
    return state

def render_dashboard(design):
    tmpl = (TEMPLATES_DIR / "dashboard.html.j2").read_text()
    project = design['project']
    team = project['name']
    panels = design['tracking']['dashboard_panels']
    milestones = design['milestones']
    roster = design['roster']

    # Build PANELS_HTML
    panels_html = []
    for p in panels:
        if p == 'milestone_timeline':
            rows = []
            for m in milestones:
                rows.append(f'<div class="milestone-row"><div class="milestone-label">{m["id"]}</div><div class="milestone-body"><div class="ms-name">{m["name"]} <span class="pill pending">pending</span></div><div class="ms-desc">{m["output"]}</div></div></div>')
            panels_html.append('<div class="panel"><div class="panel-title">Milestone timeline</div><div class="panel-intro">Project milestones with status pills.</div><div class="timeline">' + "".join(rows) + '</div></div>')
        elif p == 'team_roster_and_status':
            rows = []
            for t in roster:
                rows.append(f'<tr><td class="agent-name">{t["name"]}</td><td><span class="role-tag {t["role"]}">{t["role"]}</span></td><td><span class="pill idle">idle</span></td></tr>')
            panels_html.append(f'<div class="panel"><div class="panel-title">Team roster</div><div class="panel-intro">{len(roster)} teammates.</div><table class="roster-table">' + "".join(rows) + '</table></div>')
        elif p == 'current_pointers':
            panels_html.append('<div class="panel"><div class="panel-title">Current pointers</div><div style="font-size: 13px; line-height: 1.7;"><div><span style="color:var(--gray-500)">Brainstorm:</span> <code>—</code></div><div><span style="color:var(--gray-500)">Team plan:</span> <code>—</code></div></div></div>')
        else:
            title = p.replace('_', ' ').title()
            panels_html.append(f'<div class="panel"><div class="panel-title">{title}</div><div class="empty-state">Awaiting data. Monitor populates this from tracker events.</div></div>')

    events_html = '<div class="empty-state">No events yet. The team is just starting.</div>'

    return substitute_simple(tmpl, {
        'team': team,
        'project_display_name': project['display_name'],
        'project_basename': project['target_repo_basename'],
        'domain': project['domain'],
        'current_milestone': '—',
        'current_cohort_id': '—',
        'token_spend_cumulative_k': '0',
        'overall_status': 'initial',
        'last_update_iso': _NOW,
        'PANELS_HTML': "\n      ".join(panels_html),
        'EVENTS_HTML': events_html,
    })

# ───────── Main forge procedure ─────────

design = yaml.safe_load(DESIGN_PATH.read_text())
project = design['project']
team = project['name']
target_repo = Path(project['target_repo'])
basename = project['target_repo_basename']

# Validate (Step 1)
required_roles = {'work', 'verify', 'advise', 'tracker', 'monitor', 'orchestrator'}
present_roles = set(e['role'] for e in design['roster'])
missing = required_roles - present_roles
assert not missing, f"Role coverage failed: missing {missing}"
roster_names = set(e['name'] for e in design['roster'])
for s in design['tracking']['state_shape']:
    src = s['source']
    if src != 'lead':
        assert src in roster_names, f"Comms closure failed: {src} not in roster"
n = len(design['milestones'])
assert 1 <= n <= 5, f"Milestone count {n} out of range"  # Relaxed to 1-5
print(f"✓ Validation: {len(design['roster'])} roster entries, {n} milestones, role coverage complete")

# Step 2 — paths
agents_dir = target_repo / ".claude/agents"
team_skill_dir = target_repo / f".claude/skills/{team}-team"
hub_dir = target_repo / f".claude/team-forge/{team}"
kb_dir = target_repo / f"docs/superpowers/{basename}/{team}"
evals_dir = target_repo / f"agent_evals/{team}"
for d in [agents_dir, team_skill_dir, hub_dir / "tracker", hub_dir / "playground",
          kb_dir / "brainstorms", kb_dir / "team-plans", evals_dir]:
    d.mkdir(parents=True, exist_ok=True)
for m in design['milestones']:
    (kb_dir / "artifacts" / m['id']).mkdir(parents=True, exist_ok=True)
    (kb_dir / "runtime" / m['id']).mkdir(parents=True, exist_ok=True)

generated = []

# Step 3 — agent .md files
for entry in design['roster']:
    md, fname = render_agent_md(entry, team, basename)
    out = agents_dir / fname
    out.write_text(md)
    generated.append({"path": str(out.relative_to(target_repo)), "kind": "agent_md", "from_roster_entry": entry['name']})
    print(f"✓ agent {fname}: {md.count(chr(10)) + 1} lines")

# Step 4 — team-launcher
launcher = render_team_launcher(design)
out = team_skill_dir / "SKILL.md"
out.write_text(launcher)
generated.append({"path": str(out.relative_to(target_repo)), "kind": "team_launcher_skill"})
print(f"✓ team-launcher SKILL.md: {launcher.count(chr(10)) + 1} lines")

# Step 5 — initial status.json
status = initial_status_json(design)
out = hub_dir / "tracker" / "status.json"
out.write_text(json.dumps(status, indent=2))
generated.append({"path": str(out.relative_to(target_repo)), "kind": "tracker_initial_state"})
print(f"✓ tracker/status.json: {len(status)} top-level keys")

# Step 6 — initial dashboard
dash = render_dashboard(design)
out = hub_dir / "playground" / "dashboard.html"
out.write_text(dash)
generated.append({"path": str(out.relative_to(target_repo)), "kind": "initial_dashboard"})
(hub_dir / "playground" / "dashboard-data.json").write_text("{}\n")
print(f"✓ dashboard.html: {dash.count(chr(10)) + 1} lines")

# Step 8 — KB README
kb_readme = f"""# {project['display_name']} — `{team}` agent team KB

This directory holds the human-readable knowledge base for the `{team}` team forged for `{basename}`.

## Milestones
""" + "\n".join(f"- **{m['id']}** ({m['name']}) — go/no-go: {m['go_no_go']}" for m in design['milestones']) + f"""

## Roster
""" + "\n".join(f"- `{e['name']}` ({e['role']})" for e in design['roster']) + f"""

## Pointers
- Runtime hub: `.claude/team-forge/{team}/`
- Dashboard: `.claude/team-forge/{team}/playground/dashboard.html`
- Design contract: `.claude/team-forge/{team}/design.yaml`
"""
(kb_dir / "README.md").write_text(kb_readme)
generated.append({"path": str((kb_dir / "README.md").relative_to(target_repo)), "kind": "kb_readme"})
print(f"✓ KB README.md")

# Step 9 — manifest.json
manifest = {
    "team": team,
    "forge_version": "0.0.1",
    "design_hash": hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
    "forged_at_iso": _NOW,
    "generated_files": generated,
    "shared_agents_used": [],
}
(hub_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"✓ manifest.json: {len(generated)} files tracked")

print(f"\n=== Forge complete ===")
print(f"Team: {team}")
print(f"Files generated: {len(generated)}")
print(f"Dashboard: open {hub_dir / 'playground' / 'dashboard.html'}")
print(f"Launcher: /<team>-team (after install)")
