# Layers — where a lesson is allowed to land, and how

The SKILL.md admission rule decides *whether* a lesson applies. This decides *where*, and how
much autonomy the landing carries. The split is by blast radius: a lesson that can only hurt
this team lands now; one that changes the project's harness waits for a human; one aimed at
team-forge itself never lands from here at all.

| Layer | Scope | Targets | Autonomy |
|---|---|---|---|
| **L1** | team-local — dies with the team | `docs/team-forge/<team>/lessons.md` · `docs/team-forge/<team>/contract.yaml` `open_items` · the per-agent `MEMORY.md` files under `.claude/agent-memory/<team>-*/` · the team's gate surface — both of those last two differ by archetype, see below | **Auto-applied** once the evidence bar is met. |
| **L2** | project harness — outlives the team | `.claude/team-forge/<team>/design.yaml` (then `--resync`) · the project's `.claude/rules/` · promoted `.claude/skills/<name>/` | Lands on branch `evolve/<team>-<YYYY-MM-DD>`; **the user approves the merge.** |
| **L3** | the plugin itself | team-forge's `skills/`, `templates/`, `tools/` | **Never edited from a target repo.** Write the feedback file; filing an issue is a `user_decides` pause. |

A cycle-mode pass applies only the layers in `design.yaml`'s `evolve.cycle_mode_layers`
(default `[L1]`, validated by `forge.py`). An L2 candidate found on an unattended cycle is
written to the register as `queued` and waits for the next attended close — nobody is there to
approve a branch, and a harness change that lands while nobody is watching is indistinguishable
from drift.

**Forged agent files under `.claude/agents/` are not a target at any layer.** They are
regenerated from `design.yaml`; a hand-edit survives exactly until the next `--resync` and
then disappears without an error. Every lesson about how a worker or the lead behaves is a
`design.yaml` edit (L2) or a `MEMORY.md` note (L1), never a patch to the baked `.md`.

**Anything touching `.claude/agents/**`, `.claude/skills/**`, `.claude/rules/**`, hooks or
`settings.json` from inside a live session goes through the `fresh_session` handoff** in
`team-forge:run` — prepare the scoped brief + branch, mark it handed off, log it, and keep
going. The edit races the files the running session has loaded otherwise.

---

## L1 — team-local

### Agent memory

Judgment only: which gates are flaky and how you confirmed it, dispatch calls that turned out
wrong, approaches this codebase rejected, where the real bottleneck sat. Never task status,
progress, spend, or anything else derivable from `status.json` — duplicating live state is how
a memory starts lying.

*Which* files those are is archetype-specific, and the difference is structural rather than
cosmetic — `forge.py` emits native memory for some agents and not others:

- **workflow** — the forge emits a `<team>-lead` agent carrying `memory: project`, so
  `.claude/agent-memory/<team>-lead/MEMORY.md` is the main target, with the `worker` and
  `advisor` dispatch profiles' own dirs beside it.
- **team** — a `<team>-lead.md` *is* emitted, because `lead` is a roster entry, but it carries
  no `memory:` frontmatter, so there is no `.claude/agent-memory/<team>-lead/` for it to have.
  The orchestrator role is adopted by the main session at `/<team>-team`, and the forge gives
  native memory only to roster entries whose role is in `DISPATCHED_MEMORY_ROLES` (`advise`), at
  `.claude/agent-memory/<team>-<advisor-name>/MEMORY.md` — unless a roster entry sets `memory:`
  itself. What the orchestrator owns instead is the KB narrative under
  `docs/team-forge/<team>/`, so a lesson that would have been a lead memory note lands in the
  register below, not in a file this archetype never forged.

Append under the current cycle's section — a `## <cycle-id-or-date>` heading, one bullet per
lesson, which is the convention the lead and profile templates carry. Do not rewrite prior
sections: their repetition is what makes a memory note admissible in the first place (the same
normalized sentence in ≥ 2 cycle sections, which a single rolling paragraph cannot show). One
or two sentences per lesson, each naming what it was learned from.

Its check is the memory's own reader: the next run starts with it loaded. Record the check as
the register row that carries the same claim, so the note is not the only copy.

### The register

`docs/team-forge/<team>/lessons.md` — format, admission and supersede procedure in
`references/register-format.md`. Every applied row, every anecdote and every ablation decision
lands here; nothing else in this file is a substitute for it.

### `contract.yaml` open items

When the lesson is "this condition matters and we still cannot check it", it is an open item,
not a rule. Revise the contract through **`team-forge:contract`** — it owns the interrogation
and the lint bar (`tools/contract_lint.py`) — then land the new standing orders in the live
ledger:

```bash
python3 <team-forge>/tools/forge.py <hub>/design.yaml --sync-goal
```

`--sync-goal` re-derives `goal_directive` into the live ledger, writes only that key, and logs
a `goal_revised` event. Editing `open_items` in the KB copy alone leaves the running lead on
the old standing orders, which is a divergence nothing errors on.

Check: `python3 <team-forge>/tools/verify_contract.py docs/team-forge/<team>/contract.yaml`
exits 0, or reports the open item as an open item rather than passing silently.

### The gate surface

**Workflow** — `.claude/team-forge/<team>/gates/<descriptive-name>.{py,sh}`, the directory the
workflow forge creates. Tracked, content-descriptive names (`parity-check.py`,
`post-deletion-parity.py`), never a phase code. This is where a `gate_failure` lesson with a
stated root cause lands: the gate that missed it gets tightened, or a new one is authored
beside it.

A new gate is not applied until it is wired in. Add it to `design.yaml`'s `gates:` block and
run `--resync` so `status.json.plan.gates` carries it — that edit is L2, so a new gate is an
L1 script plus an L2 wiring row, and the wiring waits for the branch approval. Say so in the
register rather than leaving a script nothing invokes.

Check: the gate's own negative control (SKILL.md Step 6) — break what it watches, confirm red,
restore. A gate that has never been seen red has not been checked.

**Team** — the team forge creates no `gates/` directory and bakes no `plan.gates`; the
archetype's checkable equivalent is the `go_no_go` criterion on each entry in `design.yaml`'s
`milestones:`. Tightening one is a `design.yaml` edit, which is **L2** — the branch, and the
user approving it — not an auto-applied L1 script. So a `gate_failure` lesson on a team run
lands as an L1 register row now plus a queued L2 row for the criterion, and the register says
which half is still waiting. A lead may still author the script under
`.claude/team-forge/<team>/gates/` (`team-forge:run`, Memory authority) — the team forge just
never creates that directory and bakes no `plan.gates` to invoke what is in it, so the
`go_no_go` criterion has to name the script by hand or nothing ever runs it.

---

## L2 — the project harness

### `design.yaml`

`.claude/team-forge/<team>/design.yaml` is the source; the baked artifacts are derived. Edit
it, then:

```bash
python3 <team-forge>/tools/forge.py <hub>/design.yaml --check     # what is stale
python3 <team-forge>/tools/forge.py <hub>/design.yaml --resync    # land it
```

`--resync` re-bakes the ledger's `plan` block and regenerates the derived files while
preserving every live key. This is the only route for: roster and seat changes (the budget
attribution that cut a monitor seat was this edit), `gates:`, task/queue shape, `worker`
profile changes, `recurring` settings, and `evolve.cycle_mode_layers` itself.

Check: `--check` reports clean afterwards, and the harness the project already runs stays
green. Never hand-edit `status.json.plan` to shortcut it — the next re-bake silently undoes it.

### The project's `.claude/rules/` roll-up

A register row tagged project-wide is **also** proposed into the project's own rules register —
`.claude/rules/`, in the style of a versioned belief register: one version banner governing the
whole file, a claim column, a "how verified" column, and a falsified table that keeps dead
claims with what killed them.

Propose, do not merge: the row lands on the `evolve/<team>-<YYYY-MM-DD>` branch alongside everything
else L2. A rules file loads into every session in that repo, which is exactly why it is not
auto-applied — a wrong row there is re-paid on every future session of every future team.

Check: the claim's own evidence command, quoted in the row. If the row cannot carry one, it is
not ready to leave the team's register.

### Promoted skills

`.claude/skills/<name>/` — a skill this team produced from a `skill_gaps` entry. Evolve may
amend a promoted skill's body when a lesson names it, on the branch, and only when its
acceptance check still runs green afterwards. It may not promote a draft: promotion is a human
go/no-go by design (the acceptance check cannot self-certify the process that wrote it), and
evolve does not get to be the exception.

Check: re-run the skill's acceptance command. Red means restore from the snapshot and demote
the row.

---

## L3 — the plugin

team-forge's own `skills/`, `templates/` and `tools/` are never edited from a target repo. A
target repo has one team's evidence; the plugin's prompt surface is paid for by every team that
ever runs it, and a change justified by one run is exactly the accretion the ablation doctrine
exists to stop.

Write instead:

```
docs/team-forge/<team>/evolve/plugin-feedback-<YYYY-MM-DD>.md
```

Copy `<team-forge>/templates/plugin-feedback.md.j2` and fill its `{{ }}` slots by hand —
nothing renders that file, and it is the shape the plugin expects a finding to arrive in.
One section per finding: the claim, the admissible evidence with its refs, which plugin surface
it points at (skill, template, tool), and what a fix would have to check. Log the row as
`layer: L3`, `action: plugin_feedback`, `status: queued`.

Filing a GitHub issue on `shirleyfuxw/team-forge` is a **`user_decides` pause** under the
default `evolve.plugin_feedback: file` — outward-facing, so ask. A design that sets
`plugin_feedback: issue` has pre-authorized the filing; the plugin's tracker is shared by every
team on the machine, so that is a deliberate setting, never an inference. The feedback file is
written either way: it is the durable half, and it survives the answer being "not now".
