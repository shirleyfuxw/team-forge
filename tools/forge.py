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

# Extension root derived from this file's location (tools/forge.py → repo root), so the
# forge reads the templates sitting next to it — works from any clone/worktree/checkout
# and removes the previously hardcoded absolute path.
EXT_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = EXT_DIR / "templates"
# Stamped into manifest.json + status.json (forge_version). BUMP whenever a template or shared
# skill changes so already-forged teams can detect drift (forge.py --check) and re-sync.
FORGE_VERSION = "0.8.7"
# design.yaml path: first positional CLI arg, else the test fixture.
# Flags: --resync (regenerate template-derived files in place, preserve runtime state) · --check
# (report drift, read-only).
_DEFAULT_DESIGN = "/tmp/test-team-forge-greeter/.claude/team-forge/greeter/design.yaml"
_ARGV = sys.argv[1:]
_FLAGS = {a for a in _ARGV if a.startswith("--")}
_POS = [a for a in _ARGV if not a.startswith("--")]
RESYNC = "--resync" in _FLAGS
CHECK = "--check" in _FLAGS
DESIGN_PATH = Path(_POS[0] if _POS else _DEFAULT_DESIGN)
if not DESIGN_PATH.exists():
    print(f"ERROR: design.yaml not found at {DESIGN_PATH}")
    print("Usage: python3 forge.py <path-to-design.yaml> [--resync | --check]")
    sys.exit(1)
_NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ───────── Per-role text banks (mirrors forge SKILL.md) ─────────

ROLE_DESCRIPTIONS = {
    'work': "You produce primary milestone output. Receive task assignments from the lead via the shared task list — use the `TaskList` / `TaskGet` tools; the list is native to your session's team (do not hard-code a `~/.claude/tasks/...` path). Hand work off to verify-role teammates before propagation. Use `SendMessage` to coordinate with peers.",
    'verify': "You check outputs before they propagate. Read work-role outputs, validate against the milestone's go/no-go criteria, post verdicts to the lead via `SendMessage`, and report status updates to the team's ledger owner (the tracker teammate if the roster has one, otherwise the lead).",
    'advise': "You unblock work agents on hard problems. You are called on-demand via `Agent()` dispatch. **Consult your persistent agent memory first** — Claude Code injects your `MEMORY.md` (native `memory:` frontmatter): it's where you recorded patterns and ruled-out approaches from past calls, so you don't re-walk them — then read the KB slice the dispatch names. Return structured advice, and **update your memory** with what you learned. Make no writes to the team's durable KB.",
    'tracker': "You aggregate project state per the team's `tracking.state_shape` spec from design.yaml. **You are the single-writer for `.claude/team-forge/{team}/tracker/status.json`.** Read verdicts from verify-role teammates and plan outputs from the lead. Append events from `tracking.events_to_log`. Tracker is load-bearing for `/resume` — your status.json is the durable state source. Spawned FIRST on rehydrate.",
    'monitor': "You keep the dashboard always-current by PULLING authoritative state — `git rev-parse` the integration branch for the true HEAD, the `tasks[]`/gate records for progress + current task/milestone — and reconciling it against the lead's `status.json`. **Verify, don't mirror:** the lead lets rollup fields (head_sha, current_milestone, budget) go stale, so derive them; render the derived truth; and `SendMessage` the lead any drift you find. **You are the single-writer for `.claude/team-forge/{team}/playground/dashboard.html`** (per `dashboard_panels`). Trigger on every meaningful state change. Full procedure: the `team-forge:monitor` skill.",
    'orchestrator': "You are the team lead. The main session adopts this role at `/{team}-team`. You manage the shared task list, dispatch teammates, arbitrate verifier verdicts, write the team's narrative artifacts (brainstorm, plans, conclusions), and make milestone go/no-go decisions with the user. Hand each teammate a scoped brief (its task + the exact artifacts to read), not the whole KB. **You are the single-writer for `docs/team-forge/{team}/` narrative state.** If the roster has no tracker/monitor teammates (the default), you also own `.claude/team-forge/{team}/tracker/status.json` and re-render the dashboard (`python3 .claude/team-forge/{team}/playground/gen_dashboard.py`) after each update.",
}
MEMORY_AUTHORITY = {
    'tracker': "You write only to `.claude/team-forge/{team}/tracker/status.json`.",
    'monitor': "You write only to `.claude/team-forge/{team}/playground/dashboard.html` and `dashboard-data.json`.",
    'orchestrator': "You write to `docs/team-forge/{team}/{{brainstorms,team-plans,artifacts,runtime}}/`. Rosters without a tracker/monitor teammate: you also own `tracker/status.json` and the dashboard render (`gen_dashboard.py`).",
    'work': "You write to ephemeral worktrees only. No durable writes.",
    'verify': "You write to ephemeral worktrees only. No durable writes.",
    'advise': "You write to your ephemeral worktree plus your own **persistent agent-memory directory** (native `memory:` frontmatter — Claude Code auto-manages it). You make no writes to the team's durable KB.",
}

# ───────── Helpers ─────────

def substitute_simple(text, vars):
    """Replace {{var}} with vars[var]."""
    for k, v in vars.items():
        text = text.replace('{{' + k + '}}', str(v))
    return text

def json_for_script(obj):
    """JSON for embedding inside an inline <script>. Escaping `<` prevents a `</script>`
    in any string field from closing the tag early (the only HTML-context hazard)."""
    return json.dumps(obj, ensure_ascii=False).replace('<', '\\u003c')

def build_team_payload(design, status):
    """The unified dashboard payload for the agent-team archetype, built from design.yaml
    + a status dict (the initial status at forge time; the live status at monitor time).
    The shell's client-side renderer consumes exactly this shape — see monitor SKILL.md."""
    project = design['project']
    events = status.get('events') or []
    milestones = design.get('milestones', [])
    ids = [m['id'] for m in milestones]
    current_milestone = status.get('current_milestone')
    cur_idx = ids.index(current_milestone) if current_milestone in ids else None
    # A milestone is "done" when a milestone_completed event names it (preferred:
    # `milestone_id`; tolerate a bare `milestone`). Lacking that field, fall back to
    # position: with sequential milestones, everything before the active one is done.
    done_ids = {e.get('milestone_id') or e.get('milestone')
                for e in events if e.get('kind') == 'milestone_completed'}
    done_ids.discard(None)
    n_completed = sum(1 for e in events if e.get('kind') == 'milestone_completed')
    final_id = ids[-1] if ids else None
    if not events:
        overall = 'initial'
    elif final_id in done_ids or (cur_idx == len(ids) - 1 and n_completed >= len(ids) and ids):
        overall = 'completed'
    else:
        overall = 'running'
    def ms_status(mid, idx):
        if mid in done_ids:
            return 'completed'
        if cur_idx is None:
            return 'pending'
        if idx < cur_idx:
            return 'completed'
        return 'running' if idx == cur_idx else 'pending'
    return {
        'meta': {
            'team': project['name'], 'project_display_name': project['display_name'],
            'project_basename': project.get('target_repo_basename') or Path(project['target_repo']).name,
            'domain': project['domain'], 'archetype': 'team', 'overall_status': overall,
            'current_milestone': current_milestone,
            'current_cohort_id': status.get('current_cohort_id'),
            'token_spend_cumulative_k': status.get('token_spend_cumulative_k', 0),
            'last_update_iso': _NOW,
        },
        'panels': design['tracking']['dashboard_panels'],
        'milestones': [{'id': m['id'], 'name': m['name'], 'output': m.get('output', ''),
                        'status': ms_status(m['id'], i)} for i, m in enumerate(milestones)],
        'roster': [{'name': e['name'], 'role': e['role'], 'status': 'idle'} for e in design['roster']],
        'pointers': {'brainstorm': status.get('current_brainstorm'),
                     'team_plan': status.get('current_team_plan')},
        'events': (events or [])[-30:],
    }

def write_hub_gitignore(hub_dir, team):
    """Emit .claude/team-forge/<team>/.gitignore so runtime state is uniformly ephemeral.
    The dashboard is GENERATED from status.json; status.json is RUNTIME. Tracking one but
    ignoring the other produces commit noise from a generated artifact derived from ignored
    state (retro #1687, item 11). Both are ephemeral; the durable record is the KB +
    (on teardown) docs/team-forge/<team>/final-ledger.json."""
    (hub_dir / ".gitignore").write_text(
        f"# team-forge runtime state for `{team}` — ephemeral, regenerated each session.\n"
        f"# Durable knowledge is the KB at docs/team-forge/{team}/ and the design.yaml contract.\n"
        "# Do NOT track the generated dashboard or the live ledger (retro #1687, item 11).\n"
        "playground/\n"
        "tracker/status.json\n"
    )

def skills_frontmatter_block(skills):
    """YAML `skills:` frontmatter list. Preloaded (full content) when the agent runs as a
    dispatched subagent; ignored-but-documented when it runs as an agent-teams teammate."""
    if not skills:
        return ""
    return "skills:\n" + "\n".join(f"  - {s}" for s in skills)

def memory_frontmatter_block(scope):
    """YAML `memory:` frontmatter → Claude Code's native per-agent persistent-memory directory
    (`.claude/agent-memory/<name>/` for `project`; auto-injected MEMORY.md + auto-managed). Applies
    to DISPATCHED subagents; ignored when the definition runs as an agent-teams teammate (only
    tools/model apply there). Empty when scope is falsy, so teammate-only roles omit it."""
    return f"memory: {scope}" if scope else ""

# Roles that run as DISPATCHED subagents (not standing teammates) → native `memory:` takes effect.
# Default scope `project` = committable `.claude/agent-memory/<name>/`, shareable via VCS.
DISPATCHED_MEMORY_ROLES = {'advise'}

def render_skill_gap_scaffold(gap, team):
    """Render templates/skill-gap.md.j2 for one skill_gaps entry — a DRAFT scaffold."""
    tmpl = (TEMPLATES_DIR / "skill-gap.md.j2").read_text()
    return substitute_simple(tmpl, {
        'skill_name': gap['name'],
        'team': team,
        'kind': gap.get('kind', 'domain-procedure'),
        'backing': gap.get('backing', 'unspecified'),
        'purpose': gap['purpose'].rstrip(),
        'trigger': str(gap['trigger']).strip(),
        'spec': (str(gap.get('spec', '')).rstrip() or '<to be written during review>'),
        'acceptance': str(gap['acceptance']).strip(),
        'consumers': ", ".join(gap.get('consumers', [])) or 'lead',
        'adapted_from': gap.get('adapted_from', 'none — blank-page'),
    })

def emit_skill_gap_scaffolds(design, hub_dir, target_repo, generated):
    """Emit one DRAFT scaffold per skill_gaps entry into the hub's skill-drafts/.
    Drafts are NOT emitted into .claude/skills/ — promotion is a human review step."""
    gaps = design.get('skill_gaps') or []
    if not gaps:
        return
    collisions = set((design.get('asset_discovery') or {}).get('collision_list') or [])
    team = design['project']['name']
    for gap in gaps:
        for req in ('name', 'purpose', 'trigger', 'acceptance'):
            assert gap.get(req), f"skill_gaps entry missing required field '{req}'"
        assert gap['name'] not in collisions, \
            f"skill_gap '{gap['name']}' collides with an existing asset (asset_discovery.collision_list)"
        # A re-forge after promotion must not re-emit drafts for skills that already graduated.
        if (target_repo / ".claude" / "skills" / gap['name'] / "SKILL.md").exists():
            print(f"skill-gap {gap['name']}: already promoted at .claude/skills/{gap['name']}/ — skipping draft")
            continue
        d = hub_dir / "skill-drafts" / gap['name']
        d.mkdir(parents=True, exist_ok=True)
        out = d / "SKILL.md"
        out.write_text(render_skill_gap_scaffold(gap, team))
        generated.append({"path": str(out.relative_to(target_repo)), "kind": "skill_gap_scaffold", "status": "draft"})
        print(f"✓ skill-gap scaffold {gap['name']} (DRAFT — review, then promote to .claude/skills/)")

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

    # Native persistent memory only for dispatched roles (advise); teammate roles omit it
    # (Claude Code ignores `memory:` on the teammate path). An explicit entry.memory overrides.
    mem_scope = entry.get('memory', 'project' if role in DISPATCHED_MEMORY_ROLES else None)

    tmpl = (TEMPLATES_DIR / "agent.md.j2").read_text()
    purpose = entry['purpose'].rstrip()
    return substitute_simple(tmpl, {
        'agent_name': agent_name,
        'purpose': purpose,
        # Continuation lines must stay indented inside the `description: |` block,
        # or a multi-line purpose breaks the YAML frontmatter (model/skills unparseable).
        'purpose_frontmatter': purpose.replace('\n', '\n  '),
        'model': entry.get('model', 'inherit'),
        'role': role,
        'team': team,
        'project_basename': project_basename,
        'ROLE_DESCRIPTION_BLOCK': role_block,
        'SKILLS_LIST_BLOCK': skills_block,
        'SKILLS_FRONTMATTER_BLOCK': skills_frontmatter_block(skills),
        'MEMORY_FRONTMATTER_BLOCK': memory_frontmatter_block(mem_scope),
        'MEMORY_AUTHORITY_BLOCK': memory_block,
        'SHARED_AGENT_NOTE_BLOCK': shared_block,
    }), agent_name + ".md"

def roster_roles(design):
    """All roles present in the roster, including combined_roles."""
    roles = set()
    for e in design['roster']:
        if e.get('role'):
            roles.add(e['role'])
        roles.update(e.get('combined_roles') or [])
    return roles

def validate_goal(design):
    """The goal directive is what lets the lead run without stopping for input — the
    launchers' autonomy rule pauses only for user_decides items or decisions not
    inferable from it. A forge without one ships a lead that asks about everything."""
    g = design.get('goal') or {}
    assert (g.get('statement') or '').strip(), \
        "goal.statement missing — the launcher's autonomy contract needs the lead's standing orders (see templates/design.yaml.j2 `goal:`)"
    assert g.get('done_when'), "goal.done_when missing — 2-5 falsifiable completion signals (brainstorm §Completion criteria)"


def goal_block(design):
    """Markdown for the launchers' {{GOAL_BLOCK}} — the lead's standing orders."""
    g = design['goal']
    lines = [g['statement'].strip(), "", "**Done when (all of):**"]
    lines += [f"- {s}" for s in g['done_when']]
    if g.get('lead_decides'):
        lines += ["", "**You decide alone (standing approvals):**"]
        lines += [f"- {s}" for s in g['lead_decides']]
    if g.get('user_decides'):
        lines += ["", "**Always pause for the user (hard asks):**"]
        lines += [f"- {s}" for s in g['user_decides']]
    lines += ["", "Unlisted decisions default to: **act** if inferable from this directive + the "
              "ledger, **ask** otherwise — and while one question waits, keep working everything "
              "else that is eligible."]
    return "\n".join(lines)


def render_team_launcher(design):
    tmpl = (TEMPLATES_DIR / "team-launcher.md.j2").read_text()
    project = design['project']
    orchestrator = next((e for e in design['roster'] if e['role'] == 'orchestrator'), None)
    if not orchestrator:
        raise ValueError("No orchestrator in roster")
    team = project['name']
    orch_name = orchestrator['name'] if orchestrator.get('shared_across_teams') else f"{team}-{orchestrator['name']}"
    constraints_block = "\n".join(f"- {c}" for c in design.get('constraints', []))
    roles = roster_roles(design)
    ledger_lines = []
    if 'tracker' in roles:
        ledger_lines.append("The tracker teammate is the single-writer for `tracker/status.json`.")
    else:
        ledger_lines.append(f"**You** are the single-writer for `.claude/team-forge/{team}/tracker/status.json` (no tracker teammate in this roster).")
    if 'monitor' in roles:
        ledger_lines.append("The monitor teammate is the single-writer for the dashboard files.")
    else:
        ledger_lines.append(f"After each status.json update, re-render the dashboard: `python3 .claude/team-forge/{team}/playground/gen_dashboard.py` (no monitor teammate — the render step owns the dashboard).")
    return substitute_simple(tmpl, {
        'LEDGER_OWNERSHIP_BLOCK': "\n".join(ledger_lines),
        'GOAL_BLOCK': goal_block(design),
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
        'goal_directive': design['goal'],
        'current_brainstorm': None,
        'current_team_plan': None,
        'brainstorm_history': [],
        'team_plan_history': [],
        'events': [],
        'forge_metadata': {
            'forged_at_iso': _NOW,
            'design_hash': hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
            'forge_version': FORGE_VERSION,
        }
    })
    return state

def render_dashboard(design, status=None):
    """Render the self-contained interactive dashboard for the agent-team archetype by
    injecting the unified payload into the shared shell. The shell carries all CSS + the
    client-side renderer; the only substitution is the embedded data. At forge time `status`
    is the initial status.json; the monitor agent reuses the same shell + payload contract
    at runtime (see skills/monitor/SKILL.md)."""
    shell = (TEMPLATES_DIR / "dashboard.html.j2").read_text()
    payload = build_team_payload(design, status or {})
    return substitute_simple(shell, {'DASHBOARD_DATA_JSON': json_for_script(payload)}), payload

# ───────── Workflow archetype (the second fork) ─────────

def render_workflow_profile(entry, profile_role, team, project_basename):
    """Render templates/workflow/profile.md.j2 for the worker or advisor default profile."""
    agent_name = f"{team}-{profile_role}"
    skills = entry.get('skills', [])
    skills_block = "\n".join(f"- `{s}`" for s in skills) if skills else "*None proposed — inherits project + user skills at runtime.*"
    if profile_role == 'worker':
        purpose = "Shared-default coding profile. One dispatch per task in its own worktree — design-before-code, TDD, run the gate set."
        dispatch_note = ("One dispatch per task, in your own git worktree. Dispatched ONLY at fan-out points: "
                         "(a) parallel build, (b) a large self-contained task kept out of the lead's context, or "
                         "(c) independent-perspective verification. On the sequential spine the lead works inline — you stay dormant.")
        memory_note = ("Your ephemeral worktree, plus your own **persistent agent memory** (native "
                       f"`memory: project` → `.claude/agent-memory/{agent_name}/`, auto-managed by Claude "
                       "Code). Consult its `MEMORY.md` for codebase patterns/gotchas before you start; "
                       "update it when you finish. The lead owns status.json + artifacts.")
    else:  # advisor
        purpose = "Shared-default advisor profile. On-demand call to unblock the lead on hard 2+ module questions."
        dispatch_note = "An on-demand call (not a standing teammate). The lead calls you to unblock a hard 2+ module question; you return advice and stop."
        memory_note = ("Read-only on the codebase — no durable writes to the team KB. But consult and "
                       "update your own **persistent agent memory** (native `memory: project` → "
                       f"`.claude/agent-memory/{agent_name}/`) so past advice and ruled-out approaches "
                       "compound across calls. Return structured advice.")
    tmpl = (TEMPLATES_DIR / "workflow" / "profile.md.j2").read_text()
    return substitute_simple(tmpl, {
        'agent_name': agent_name,
        'purpose': purpose,
        'model': entry.get('model', 'inherit'),
        'profile_role': profile_role,
        'team': team,
        'project_basename': project_basename,
        'procedure': str(entry.get('procedure', '')).rstrip(),
        'SKILLS_LIST_BLOCK': skills_block,
        'SKILLS_FRONTMATTER_BLOCK': skills_frontmatter_block(skills),
        'MEMORY_FRONTMATTER_BLOCK': memory_frontmatter_block(entry.get('memory', 'project')),
        'DISPATCH_NOTE': dispatch_note,
        'MEMORY_NOTE': memory_note,
    }), agent_name + ".md"


def observability_block(design):
    """Who owns the dashboard at runtime — a monitor teammate, the lead + render step,
    or (one-shot default) nobody: the ledger itself is the observability surface.
    Injected into the workflow launchers as {{OBSERVABILITY_BLOCK}}."""
    team = design['project']['name']
    if not workflow_wants_dashboard(design):
        return (
            "No dashboard for this one-shot workflow — **the ledger is the observability "
            f"surface**. Keep `.claude/team-forge/{team}/tracker/status.json` current (per-task "
            "status, events, budget) after every meaningful state change; anyone checking progress "
            "reads it or `TASKS.yaml` directly. (To add a rendered dashboard later, set "
            "`ledger.dashboard: true` in design.yaml and re-forge/`--resync`.)"
        )
    if design.get('ledger', {}).get('dashboard_owner') == 'monitor_agent':
        agent = f"{team}-{(design['ledger'].get('monitor') or {}).get('name', 'monitor')}"
        return (
            f"A **monitor teammate** (`{agent}`) owns the dashboard — do NOT run `gen_dashboard.py` yourself.\n"
            f"- **Spawn** `{agent}` at launch; **rehydrate** it on `/resume` (respawn with context).\n"
            "- After each ledger update (task done / commit / cycle boundary), **trigger** it via "
            "`SendMessage`. It PULLS authoritative state (git HEAD of the integration branch, the "
            "`tasks[]`/gate records), reconciles against your `status.json`, rewrites the dashboard, and "
            "messages back any **drift** — a rollup field you left stale (`integration_branch.head_sha`, "
            "`integration_branch.pr_url`, `budget`). Fix the flagged fields in `status.json`.\n"
            "- It is single-writer for `dashboard.html` / `dashboard-data.json`; you stay single-writer for `status.json`."
        )
    return (
        f"No monitor teammate — **you** own the dashboard. After each ledger update run "
        f"`python3 .claude/team-forge/{team}/playground/gen_dashboard.py`. It DERIVES "
        "`integration_branch.head_sha` (via `git rev-parse`) and `current_task` (from the task "
        "records), so those panels stay correct even if you didn't hand-update the rollup — but you "
        "must still refresh `integration_branch.pr_url` / `budget` in `status.json` yourself."
    )


def render_workflow_launcher(design):
    tmpl = (TEMPLATES_DIR / "workflow-launcher.md.j2").read_text()
    project = design['project']
    constraints_block = "\n".join(f"- {c}" for c in design.get('constraints', []))
    return substitute_simple(tmpl, {
        'team': project['name'],
        'project_display_name': project['display_name'],
        'project_name': project['name'],
        'project_basename': project['target_repo_basename'],
        'target_repo': project['target_repo'],
        'domain': project['domain'],
        'integration_branch': project.get('integration_branch', '(unset)'),
        'GOAL_BLOCK': goal_block(design),
        'CONSTRAINTS_BULLET_LIST': constraints_block,
        'OBSERVABILITY_BLOCK': observability_block(design),
    })


def render_workflow_drain_launcher(design):
    tmpl = (TEMPLATES_DIR / "workflow-drain-launcher.md.j2").read_text()
    project = design['project']
    constraints_block = "\n".join(f"- {c}" for c in design.get('constraints', []))
    rec = design.get('recurring')
    team = project['name']
    if rec:
        recurring_note = (f"**Recurring / unattended.** Schedule: {rec.get('schedule', '—')}. "
                          f"Cycle box: {rec.get('cycle_box', '—')}. Unattended: {rec.get('unattended', False)} "
                          f"(plan-gate items park for human approval; per-item verify gates mandatory). "
                          f"Carry-over via {rec.get('carry_over_state', 'status.json')}. "
                          f"The schedule is the OUTER loop — this skill runs ONE cycle and exits.")
        next_cycle_note = "The schedule fires the next cycle."
        teardown_note = (
            "**Retiring the recurring workflow** (not per-cycle): when the drain is decommissioned, run\n"
            "**`team-forge:teardown`** — it removes the schedule/cron trigger first (so no further cycles fire),\n"
            "archives the ledger, prunes worktrees, and removes the launcher + profiles + ephemeral state.")
    else:
        recurring_note = "One-shot (not recurring): drains the queue once, then exits."
        next_cycle_note = ("This is a **one-shot** drain — there is no next cycle and no schedule; "
                           "when the queue is empty the workflow is done.")
        teardown_note = (
            "**Retiring the workflow:** once the drain is done and its PRs are merged/closed, run\n"
            "**`team-forge:teardown`** — it archives the ledger, prunes worktrees, and removes the\n"
            "launcher + profiles + ephemeral state. (No schedule/cron to remove — this is one-shot.)")
    # advisor is an OPTIONAL profile; only point at it if it was actually forged, else the
    # escalation pointer dangles at a non-existent agent.
    if 'advisor' in design:
        escalation_note = f"Escalate hard\n  2+-module questions to **advisor** (`{team}-advisor`)."
    else:
        escalation_note = ("Escalate hard\n  2+-module questions to the **lead** "
                           "(no advisor profile in this workflow) — surface it and stop.")
    # wave_size belongs in the numeric "waves of ≤ N" slot; if the design put prose there,
    # keep the prose out of the launcher (it lives in queue.wave_size / TASKS.yaml) and render a
    # clean pointer instead, so the slot never reads as a run-on paragraph mid-sentence.
    ws = design.get('queue', {}).get('wave_size', 4)
    wave_size = str(ws) if isinstance(ws, int) else "the per-stage cap in `queue.wave_size` (see TASKS.yaml)"
    return substitute_simple(tmpl, {
        'team': team,
        'project_display_name': project['display_name'],
        'project_name': project['name'],
        'project_basename': project['target_repo_basename'],
        'target_repo': project['target_repo'],
        'domain': project['domain'],
        'integration_branch': project.get('integration_branch', '(unset)'),
        'WAVE_SIZE': wave_size,
        'GOAL_BLOCK': goal_block(design),
        'RECURRING_NOTE': recurring_note,
        'NEXT_CYCLE_NOTE': next_cycle_note,
        'TEARDOWN_NOTE': teardown_note,
        'ESCALATION_NOTE': escalation_note,
        'CONSTRAINTS_BULLET_LIST': constraints_block,
        'OBSERVABILITY_BLOCK': observability_block(design),
    })


def dashboard_panel_registry():
    """Valid panel ids = the renderer keys in dashboard.html.j2. The template is the single
    source of truth so a new renderer becomes a valid id without touching this file."""
    shell = (TEMPLATES_DIR / "dashboard.html.j2").read_text()
    ids = re.findall(r'^    (\w+): function \(d\)', shell, re.M)
    assert ids, "could not extract the panel renderer registry from dashboard.html.j2"
    return ids


def validate_dashboard_panels(panels, context):
    """An unknown panel id renders a healthy-looking page whose panel is a placeholder
    forever — the alpha-onboarding-completeness run shipped four of those for a week.
    Fail at forge time instead."""
    valid = dashboard_panel_registry()
    bad = [p for p in (panels or []) if p not in valid]
    assert not bad, (
        f"{context}: dashboard_panels entries {bad!r} are not renderer ids. Panels must be "
        f"chosen from the shell's registry — anything else renders as a silent empty-state "
        f"box. Valid ids: {sorted(valid)}. Describe panel intent in YAML comments, not in the list.")


def workflow_wants_dashboard(design):
    """One-shot workflows default to NO dashboard: status.json + TASKS.yaml is the whole
    ledger, and the render loop only earns its keep on recurring/long-running work.
    ledger.dashboard: true opts in explicitly; a recurring schedule or a monitor
    dashboard-owner implies it."""
    ledger = design.get('ledger', {})
    if 'dashboard' in ledger:
        return bool(ledger['dashboard'])
    return bool(design.get('recurring')) or ledger.get('dashboard_owner') == 'monitor_agent'


def render_gen_dashboard(design):
    """Emit the deterministic runtime dashboard renderer (either archetype). It bakes the
    shared shell as a constant so the emitted script is self-contained and never depends on
    the extension being present at runtime. At runtime gen_dashboard.py builds the unified
    payload from status.json and injects it into that shell. Workflow teams always get it;
    agent-teams get it when the roster has no monitor teammate (the render step replaces
    the standing agent — design-time facts like milestones/roster are baked in)."""
    tmpl = (TEMPLATES_DIR / "gen_dashboard.py.j2").read_text()
    project = design['project']
    shell = (TEMPLATES_DIR / "dashboard.html.j2").read_text()
    is_workflow = design.get('archetype') == 'workflow'
    panels = (design['ledger'] if is_workflow else design['tracking'])['dashboard_panels']
    milestones = [] if is_workflow else [
        {'id': m['id'], 'name': m['name'], 'output': m.get('output', '')}
        for m in design.get('milestones', [])]
    roster = [] if is_workflow else [
        {'name': e['name'], 'role': e.get('role') or '+'.join(e.get('combined_roles') or []), 'status': 'idle'}
        for e in design['roster']]
    return substitute_simple(tmpl, {
        'team': project['name'],
        'project_display_name': project['display_name'],
        'project_basename': project.get('target_repo_basename') or Path(project['target_repo']).name,
        'domain': project['domain'],
        'archetype': 'workflow' if is_workflow else 'team',
        'DASHBOARD_PANELS_JSON': json.dumps(panels),
        'MILESTONES_JSON': json.dumps(milestones),
        'ROSTER_JSON': json.dumps(roster),
        'DASHBOARD_SHELL_JSON': json.dumps(shell),  # valid Python str literal too
    })


def initial_status_json_workflow(design):
    state = {}
    for s in design['ledger']['state_shape']:
        state[s['id']] = {'string': None, 'int': 0, 'float': 0.0, 'bool': False, 'list': [], 'object': {}}[s['type']]
    tasks = design.get('tasks', [])
    if tasks:
        state['tasks'] = [{'id': t['id'], 'status': 'pending', 'gate_status': None, 'commit': None} for t in tasks]
        state['current_task'] = tasks[0]['id']
    state['integration_branch'] = {'name': design['project'].get('integration_branch'), 'head_sha': None, 'pr_url': None}
    state['goal_directive'] = design['goal']
    state['events'] = []
    state['forge_metadata'] = {
        'forged_at_iso': _NOW,
        'design_hash': hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
        'forge_version': FORGE_VERSION, 'archetype': 'workflow', 'shape': design.get('shape'),
    }
    return state


def validate_workflow(design):
    assert design.get('shape') in ('sequential-gated', 'parallel-drain'), f"bad/missing shape: {design.get('shape')}"
    validate_goal(design)
    assert design.get('gates'), "no gates block"
    assert 'worker' in design, "no worker profile"
    assert design.get('ledger', {}).get('state_shape'), "no ledger.state_shape"
    dbo = design.get('ledger', {}).get('dashboard_owner', 'render_step')
    assert dbo in ('render_step', 'monitor_agent'), f"bad ledger.dashboard_owner: {dbo!r} (render_step|monitor_agent)"
    if workflow_wants_dashboard(design):
        panels = design['ledger'].get('dashboard_panels')
        assert panels, "dashboard requested (recurring / ledger.dashboard / monitor owner) but no ledger.dashboard_panels"
        validate_dashboard_panels(panels, "ledger")
    gate_names = set(design['gates'].keys())
    if design['shape'] == 'sequential-gated':
        tasks = design.get('tasks')
        assert tasks, "sequential-gated needs a tasks list"
        ids = [t['id'] for t in tasks]
        assert len(ids) == len(set(ids)), "duplicate task ids"
        idset = set(ids)
        for t in tasks:
            assert t.get('dispatch', 'inline') in ('inline', 'worker', 'fresh_session'), f"{t['id']}: bad dispatch (inline|worker|fresh_session)"
            for g in t.get('gate_set', []):
                assert g in gate_names, f"{t['id']}: gate '{g}' not in gates vocabulary"
            for dep in t.get('depends_on', []):
                assert dep in idset, f"{t['id']}: depends_on '{dep}' is not a task"
        indeg = {i: 0 for i in ids}
        adj = {i: [] for i in ids}
        for t in tasks:
            for dep in t.get('depends_on', []):
                adj[dep].append(t['id']); indeg[t['id']] += 1
        q = [i for i in ids if indeg[i] == 0]; seen = 0
        while q:
            n = q.pop(); seen += 1
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0: q.append(m)
        assert seen == len(ids), "task DAG has a cycle"
    else:
        assert design.get('queue'), "parallel-drain needs a queue block"
        # wave_size feeds the launcher's numeric "waves of ≤ N" slot. Prose there renders as a
        # run-on paragraph mid-sentence (the render step now falls back to a TASKS.yaml pointer,
        # but the design is still malformed) — warn so it gets fixed at the source.
        ws = design['queue'].get('wave_size', 4)
        if not isinstance(ws, int):
            print(f"⚠ queue.wave_size is {type(ws).__name__}, not int — the launcher will point at "
                  "TASKS.yaml instead of a number. Put the numeric per-wave cap in wave_size and move "
                  "the sizing rationale to queue.triage / a YAML comment.")
    ws_detail = design.get('queue', {}).get('wave_size', '?') if design['shape'] == 'parallel-drain' else None
    detail = (f"{len(design['tasks'])} tasks, DAG acyclic" if design['shape'] == 'sequential-gated'
              else f"queue (wave {ws_detail if isinstance(ws_detail, int) else 'per-triage'})")
    print(f"✓ Validation (workflow/{design['shape']}): {len(gate_names)} gates, {detail}")


def forge_workflow(design):
    import subprocess
    project = design['project']
    team = project['name']
    target_repo = Path(project['target_repo'])
    basename = project.get('target_repo_basename') or Path(project['target_repo']).name

    validate_workflow(design)

    agents_dir = target_repo / ".claude/agents"
    skill_dir = target_repo / f".claude/skills/{team}-workflow"
    hub_dir = target_repo / f".claude/team-forge/{team}"
    kb_dir = target_repo / f"docs/team-forge/{team}"
    evals_dir = target_repo / f"agent_evals/{team}"
    for d in [agents_dir, skill_dir, hub_dir / "tracker", hub_dir / "playground",
              hub_dir / "gates", kb_dir / "brainstorms", kb_dir / "team-plans", evals_dir]:
        d.mkdir(parents=True, exist_ok=True)
    for t in design.get('tasks', []):
        (kb_dir / "artifacts" / t['id']).mkdir(parents=True, exist_ok=True)
        (kb_dir / "runtime" / t['id']).mkdir(parents=True, exist_ok=True)

    generated = []
    write_hub_gitignore(hub_dir, team)
    generated.append({"path": str((hub_dir / '.gitignore').relative_to(target_repo)), "kind": "hub_gitignore"})

    for role in ('worker', 'advisor'):
        if role in design:
            md, fname = render_workflow_profile(design[role], role, team, basename)
            (agents_dir / fname).write_text(md)
            generated.append({"path": str((agents_dir / fname).relative_to(target_repo)), "kind": "workflow_profile"})
            print(f"✓ profile {fname}: {md.count(chr(10)) + 1} lines")

    # Skill-gap scaffolds — the primary deliverable (skills outlive the team; W5).
    emit_skill_gap_scaffolds(design, hub_dir, target_repo, generated)

    launcher = render_workflow_drain_launcher(design) if design['shape'] == 'parallel-drain' else render_workflow_launcher(design)
    (skill_dir / "SKILL.md").write_text(launcher)
    generated.append({"path": str((skill_dir / 'SKILL.md').relative_to(target_repo)), "kind": "workflow_launcher_skill"})
    print(f"✓ {design['shape']} launcher SKILL.md: {launcher.count(chr(10)) + 1} lines")

    # TASKS.yaml — the live runtime work list (tasks + gates [+ queue])
    tasks_doc = {'gates': design['gates']}
    if 'tasks' in design: tasks_doc = {'tasks': design['tasks'], **tasks_doc}
    if 'queue' in design: tasks_doc['queue'] = design['queue']
    tasks_yaml = (f"# TASKS.yaml — live runtime work list for the {team} workflow.\n"
                  "# Lead-editable: re-cut not-yet-done tasks + gates when the design pivots (W7).\n\n"
                  + yaml.safe_dump(tasks_doc, sort_keys=False, allow_unicode=True))
    (hub_dir / "TASKS.yaml").write_text(tasks_yaml)
    generated.append({"path": str((hub_dir / 'TASKS.yaml').relative_to(target_repo)), "kind": "tasks_yaml"})
    print(f"✓ TASKS.yaml: {len(design.get('tasks', []))} tasks, {len(design['gates'])} gates")

    shutil.copyfile(DESIGN_PATH, hub_dir / "design.yaml")
    generated.append({"path": str((hub_dir / 'design.yaml').relative_to(target_repo)), "kind": "design_contract"})

    status = initial_status_json_workflow(design)
    (hub_dir / "tracker" / "status.json").write_text(json.dumps(status, indent=2))
    generated.append({"path": str((hub_dir / 'tracker' / 'status.json').relative_to(target_repo)), "kind": "ledger_initial_state"})
    print(f"✓ tracker/status.json: {len(status)} top-level keys")

    if workflow_wants_dashboard(design):
        gd_path = hub_dir / "playground" / "gen_dashboard.py"
        gd_path.write_text(render_gen_dashboard(design))
        generated.append({"path": str(gd_path.relative_to(target_repo)), "kind": "dashboard_renderer"})
        r = subprocess.run([sys.executable, str(gd_path)], capture_output=True, text=True)
        if r.returncode != 0:
            print("⚠ gen_dashboard.py failed:\n" + r.stderr)
        else:
            generated.append({"path": str((hub_dir / 'playground' / 'dashboard.html').relative_to(target_repo)), "kind": "initial_dashboard"})
            print("✓ dashboard.html rendered via gen_dashboard.py")
    else:
        print("– dashboard skipped (one-shot workflow — the ledger IS the observability "
              "surface; set ledger.dashboard: true to emit one)")

    # Optional monitor teammate — ledger.dashboard_owner == 'monitor_agent'. gen_dashboard.py is
    # still emitted above: the monitor uses it as its deterministic renderer and adds live
    # authoritative-pull (git HEAD, task records) + drift alerts on top (see skills/monitor).
    if design.get('ledger', {}).get('dashboard_owner') == 'monitor_agent':
        mon = design['ledger'].get('monitor') or {}
        entry = {
            'name': mon.get('name', 'monitor'),
            'role': 'monitor',
            'model': mon.get('model', 'inherit'),
            'skills': mon.get('skills', ['team-forge:monitor']),
            'purpose': mon.get('purpose',
                f"Keep the {team} dashboard always-current: pull authoritative state (git HEAD of "
                f"{project.get('integration_branch', 'the integration branch')}, the task/gate "
                "records), reconcile against the lead's status.json, rewrite the dashboard, and "
                "flag any stale-rollup drift back to the lead."),
        }
        md, fname = render_agent_md(entry, team, basename)
        (agents_dir / fname).write_text(md)
        generated.append({"path": str((agents_dir / fname).relative_to(target_repo)), "kind": "monitor_agent"})
        print(f"✓ monitor agent {fname}")

    kb_readme = (f"# {project['display_name']} — `{team}` workflow KB\n\n"
                 f"Workflow archetype ({design['shape']}). Work list + gates: "
                 f"`.claude/team-forge/{team}/TASKS.yaml`; progress: `tracker/status.json`.\n\n## Tasks\n"
                 + "\n".join(f"- **{t['id']}** ({t['name']}) — gates: {t.get('gate_set', [])}" for t in design.get('tasks', []))
                 + f"\n\n## Pointers\n- Launcher: `/{team}-workflow`\n"
                 + (f"- Dashboard: `.claude/team-forge/{team}/playground/dashboard.html`\n"
                    if workflow_wants_dashboard(design)
                    else f"- Progress: `.claude/team-forge/{team}/tracker/status.json` (no dashboard — one-shot workflow)\n"))
    (kb_dir / "README.md").write_text(kb_readme)
    generated.append({"path": str((kb_dir / 'README.md').relative_to(target_repo)), "kind": "kb_readme"})
    print("✓ KB README.md")

    manifest = {
        "team": team, "archetype": "workflow", "shape": design['shape'], "forge_version": FORGE_VERSION,
        "design_hash": hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
        "forged_at_iso": _NOW, "generated_files": generated,
    }
    (hub_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"✓ manifest.json: {len(generated)} files tracked")

    print("\n=== Workflow forge complete ===")
    print(f"Team: {team} ({design['shape']}) · {len(generated)} files")
    print(f"Launcher: /{team}-workflow")
    if workflow_wants_dashboard(design):
        print(f"Dashboard: open {hub_dir / 'playground' / 'dashboard.html'}")
    else:
        print(f"Progress: {hub_dir / 'tracker' / 'status.json'} (no dashboard — one-shot workflow)")
    drafts_emitted = sum(1 for g in generated if g.get('kind') == 'skill_gap_scaffold')
    if drafts_emitted:
        print(f"⚠ {drafts_emitted} skill-gap DRAFT(s) in {hub_dir / 'skill-drafts'} — "
              "review against each scaffold's promotion checklist, then promote to .claude/skills/. "
              "Gates that call an unpromoted skill fail-closed.")


# ───────── Re-sync: propagate template/skill updates into an already-forged team ─────────
# Template-derived files are frozen copies (self-contained by design). --resync regenerates
# ONLY these from the current templates + the team's own design.yaml, preserving all runtime
# state (status.json, TASKS.yaml, artifacts, promoted skill-drafts). Everything not listed here
# is runtime/human-owned and is left untouched.

def _regen_content(design, team, basename, fmeta):
    """Regenerated text for a template-derived manifest entry, or None to preserve the file."""
    kind = fmeta.get('kind')
    if kind == 'team_launcher_skill':
        return render_team_launcher(design)
    if kind == 'workflow_launcher_skill':
        return (render_workflow_drain_launcher(design) if design.get('shape') == 'parallel-drain'
                else render_workflow_launcher(design))
    if kind == 'dashboard_renderer':
        return render_gen_dashboard(design)
    if kind == 'agent_md':
        e = next((r for r in design.get('roster', []) if r['name'] == fmeta.get('from_roster_entry')), None)
        return render_agent_md(e, team, basename)[0] if e else None
    if kind == 'workflow_profile':
        role = 'advisor' if fmeta.get('path', '').endswith('-advisor.md') else 'worker'
        return render_workflow_profile(design[role], role, team, basename)[0] if role in design else None
    if kind == 'monitor_agent':
        mon = (design.get('ledger') or {}).get('monitor') or {}
        e = {'name': mon.get('name', 'monitor'), 'role': 'monitor',
             'model': mon.get('model', 'inherit'),
             'skills': mon.get('skills', ['team-forge:monitor']),
             'purpose': mon.get('purpose', f"Keep the {team} dashboard always-current by pulling authoritative state.")}
        return render_agent_md(e, team, basename)[0]
    return None   # tracker/ledger state, TASKS.yaml, design copy, skill-drafts, README, gitignore → preserve


def resync(design, target_repo, team, basename, do_write):
    """Regenerate template-derived files from the CURRENT templates, preserving runtime state.
    do_write=False is --check (report drift only)."""
    manifest_path = target_repo / f".claude/team-forge/{team}/manifest.json"
    if not manifest_path.exists():
        print(f"✗ no manifest at {manifest_path} — team not forged here. Run a full forge first.")
        sys.exit(1)
    manifest = json.loads(manifest_path.read_text())
    old_ver = manifest.get('forge_version', '?')
    changed, absent = [], []
    for fmeta in manifest.get('generated_files', []):
        content = _regen_content(design, team, basename, fmeta)
        if content is None:
            continue                                    # runtime/human-owned → preserve
        p = target_repo / fmeta['path']
        if not p.exists():
            absent.append(fmeta['path']); continue      # deleted/promoted → don't recreate
        if p.read_text() != content:
            changed.append(fmeta['path'])
            if do_write:
                p.write_text(content)
    print(f"Team {team}: forged at {old_ver}, current templates {FORGE_VERSION} — "
          f"{'STALE' if old_ver != FORGE_VERSION else 'version matches'}")
    if do_write:
        manifest['forge_version'] = FORGE_VERSION
        manifest['resynced_at_iso'] = _NOW
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"✓ resync: regenerated {len(changed)} template-derived file(s); runtime state preserved.")
    else:
        print(f"{'⚠ ' if changed else '✓ '}{len(changed)} template-derived file(s) would change on --resync:")
    for c in changed:
        print(f"   ↻ {c}")
    for a in absent:
        print(f"   – {a} (absent — skipped; re-forge or promote manually if needed)")
    if not changed and old_ver == FORGE_VERSION:
        print("   (already current)")


# ───────── Main forge procedure ─────────

design = yaml.safe_load(DESIGN_PATH.read_text())
project = design['project']
team = project['name']
target_repo = Path(project['target_repo'])
# target_repo_basename is OPTIONAL + display-only (never a durable-path component); derive it
# from target_repo when absent so paths never depend on the config field being set (retro #1687, item 3).
basename = project.get('target_repo_basename') or Path(project['target_repo']).name
project['target_repo_basename'] = basename   # normalize so all downstream reads succeed

# Re-sync / drift-check: regenerate template-derived files in place (preserve runtime), then exit.
if RESYNC or CHECK:
    resync(design, target_repo, team, basename, do_write=RESYNC)
    sys.exit(0)

# Fork on archetype: workflow takes the lead-loop path and exits; default is the team path.
if design.get('archetype') == 'workflow':
    forge_workflow(design)
    sys.exit(0)

# Validate (Step 1) — tracker/monitor are OPTIONAL roles: the default is a lead-written
# ledger + a deterministic dashboard render step (gen_dashboard.py), mirroring the
# workflow archetype. Add them to the roster only when tracking load justifies standing agents.
required_roles = {'work', 'verify', 'advise', 'orchestrator'}
present_roles = roster_roles(design)
missing = required_roles - present_roles
assert not missing, f"Role coverage failed: missing {missing}"
roster_names = set(e['name'] for e in design['roster'])
for s in design['tracking']['state_shape']:
    src = s['source']
    if src != 'lead':
        assert src in roster_names, f"Comms closure failed: {src} not in roster"
validate_goal(design)
validate_dashboard_panels(design['tracking'].get('dashboard_panels'), "tracking")
n = len(design['milestones'])
assert 1 <= n <= 5, f"Milestone count {n} out of range"  # Relaxed to 1-5
print(f"✓ Validation: {len(design['roster'])} roster entries, {n} milestones, role coverage complete")

# Step 2 — paths
agents_dir = target_repo / ".claude/agents"
team_skill_dir = target_repo / f".claude/skills/{team}-team"
hub_dir = target_repo / f".claude/team-forge/{team}"
kb_dir = target_repo / f"docs/team-forge/{team}"
evals_dir = target_repo / f"agent_evals/{team}"
for d in [agents_dir, team_skill_dir, hub_dir / "tracker", hub_dir / "playground",
          kb_dir / "brainstorms", kb_dir / "team-plans", evals_dir]:
    d.mkdir(parents=True, exist_ok=True)
for m in design['milestones']:
    (kb_dir / "artifacts" / m['id']).mkdir(parents=True, exist_ok=True)
    (kb_dir / "runtime" / m['id']).mkdir(parents=True, exist_ok=True)

generated = []
write_hub_gitignore(hub_dir, team)
generated.append({"path": str((hub_dir / '.gitignore').relative_to(target_repo)), "kind": "hub_gitignore"})

# Stash the design contract in the hub (parity with the workflow path) so --check / --resync
# and the launcher's staleness note resolve `.claude/team-forge/<team>/design.yaml`.
shutil.copyfile(DESIGN_PATH, hub_dir / "design.yaml")
generated.append({"path": str((hub_dir / "design.yaml").relative_to(target_repo)), "kind": "design_contract"})
print("✓ design.yaml stashed in hub")

# Step 3 — agent .md files
for entry in design['roster']:
    md, fname = render_agent_md(entry, team, basename)
    out = agents_dir / fname
    out.write_text(md)
    generated.append({"path": str(out.relative_to(target_repo)), "kind": "agent_md", "from_roster_entry": entry['name']})
    print(f"✓ agent {fname}: {md.count(chr(10)) + 1} lines")

# Step 3b — skill-gap scaffolds (the primary deliverable; drafts pending human promotion)
emit_skill_gap_scaffolds(design, hub_dir, target_repo, generated)

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

# Step 6 — initial dashboard (self-contained interactive shell + embedded payload)
dash, dash_payload = render_dashboard(design, status)
out = hub_dir / "playground" / "dashboard.html"
out.write_text(dash)
generated.append({"path": str(out.relative_to(target_repo)), "kind": "initial_dashboard"})
(hub_dir / "playground" / "dashboard-data.json").write_text(json.dumps(dash_payload, indent=2) + "\n")
print(f"✓ dashboard.html: {dash.count(chr(10)) + 1} lines (self-contained, interactive)")

# Step 6b — no monitor teammate → emit the deterministic runtime renderer instead
# (the lead re-runs it after each status.json update; same render step as workflow).
if 'monitor' not in present_roles:
    gd_path = hub_dir / "playground" / "gen_dashboard.py"
    gd_path.write_text(render_gen_dashboard(design))
    generated.append({"path": str(gd_path.relative_to(target_repo)), "kind": "dashboard_renderer"})
    print("✓ gen_dashboard.py (no monitor in roster — the render step owns dashboard re-renders)")

# Step 8 — KB README
kb_readme = f"""# {project['display_name']} — `{team}` agent team KB

This directory holds the human-readable knowledge base for the `{team}` team.

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
    "forge_version": FORGE_VERSION,
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
_drafts_emitted = sum(1 for g in generated if g.get('kind') == 'skill_gap_scaffold')
if _drafts_emitted:
    print(f"⚠ {_drafts_emitted} skill-gap DRAFT(s) in {hub_dir / 'skill-drafts'} — "
          "review against each scaffold's promotion checklist, then promote to .claude/skills/.")
