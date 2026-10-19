---
name: team-forge:evolve
description: |
  Use when a run has finished producing evidence and something should be learned from
  it — a forged run reaching Close, a recurring workflow closing a cycle, someone
  asking what a run taught us or for a retro / post-mortem / process-improvement
  write-up, and always just before team-forge:teardown archives the ledger. Mines the
  run's own artifacts (ledger events, gate results, budget attribution, agent
  memory) for lessons that carry evidence, applies them by layer — team-local
  automatically, project harness on a branch, plugin feedback never — and records every
  one in docs/team-forge/<team>/lessons.md. Not for mid-run work: a task finishing is
  not a cycle closing.
---

# team-forge:evolve — apply what the run proved, record what it only suggested

A run leaves evidence behind and nothing harvests it. A real ticket-drain workflow ended
with a 257-event ledger, a gate matrix, a budget line showing one team at 1010% of its soft
target, and an `agent-memory/…/MEMORY.md` full of hard-won gotchas — and the lessons still
reached the repo by hand: a 214-line retro someone wrote from scratch, ~35 post-run repair
commits that hand-edited forged agents and `design.yaml`, and a memory note about a hook
false positive that took two months to become a code fix. This skill is that pass, run
deterministically, at every cycle end and once at Close.

Evolve is the fifth phase: contract → design → forge → **run** → **evolve** → teardown. It
runs *before* teardown, because teardown deletes exactly the artifacts evolve mines.

## Principle — evidence applies, anecdote records

A lesson is **applied** only when the run can show it happened more than once, or hurt once
in a way with a name. Everything else is recorded and left alone. Six admissible signals:

| Signal | What admits it |
|---|---|
| `recurrence` | The same normalized event kind occurs ≥ 2 times, or a payload counter says so — an `occurrence`/`instance`/`tally` field, or a kind naming "second"/"third"/"rediscovered". |
| `blocked_resolved` | An `agent_blocked` event with a later matching resolution (same agent + same issue key) carrying `status: resolved` or a workaround/resolution field. The workaround is the lesson. |
| `gate_failure` | A gate failure whose payload carries a `root_cause` or `reason`. A red gate with no stated cause is not evidence, it is a mood. |
| `budget_attribution` | A budget line above `evolve.budget_overrun_factor` (default 3) × its soft target, with the spend attributed. "Six monitor dashboard renders at ~116k each" is what got that seat cut — the attribution, not the total. |
| `policy_adopted` | Admissible by definition: a `policy_adopted` event is a rule the lead already applied mid-run that lives in no file. It is running unwritten; writing it down is the whole job. |
| `lesson_event` | A `lesson` event whose `payload.status` is not `candidate`. |

Everything else is an **anecdote**: it goes to the register's Candidates table and is never
applied. A single lead-invented event kind is an anecdote — that 257-event run logged 78
distinct kinds and ~50 of them appeared exactly once, because the lead minted a noun for
something the schema had no slot for. Fifty one-offs are fifty design defects, not fifty
rules.

A note in an agent's `MEMORY.md` — the workflow lead's, or a team's dispatched advisors' — is
admissible only when the same normalized sentence appears in ≥ 2 `## <cycle-or-date>` sections
of that file, or when it corroborates a candidate mined from **this run's own ledger**. A
sighting in another instance's or another team's run does not count: it is that run's evidence,
not this one's. A memory line this pass writes or merges holds judgment only, never live state
("while it is open", a count, a status), because the line outlives the state it copies. Memory
is judgment, and judgment repeated is the only judgment this phase can check.

A `lesson` event's `evidence.type` names one of the six signals above, `memory_note` for a note
admitted under this bar, or `anecdote` — `EVIDENCE_TYPES` in `tools/ledger_vocab.py`, which
`team-forge:run` prints the same way.

## When to use

- The run reached Close in `team-forge:run` — every `done_when` check green, before the
  branch is handed over and before `team-forge:teardown`.
- A recurring workflow closed a cycle (the drain loop's Step 4).
- The user asks what the run taught us, for a retro, a post-mortem, or a process-improvement
  plan.

Do **not** fire on an ordinary mid-run task. A task completing, a gate going green, a wave
draining — none of those is a cycle boundary, and mining a run that is still moving produces
recurrence counts that change under you.

## Procedure

### Step 1 — Resolve the hub and the mode

Resolve the hub once, from the main checkout:
`dirname $(git rev-parse --path-format=absolute --git-common-dir)`. Never resolve it against
your CWD. A linked worktree receives no gitignored files, so `tracker/status.json` is *absent*
there rather than stale, and the tracked hub files read back at the branch's committed state
instead of the live one — an evolve pass run from a worktree mines a ledger that does not
exist and reports zero events with a straight face. Every path below is relative to that root.

Then fix the mode, which decides which layers are in play:

- **`close`** — invoked from the run's Close. All three layers (see `references/layers.md`).
- **`cycle`** — invoked from a recurring cycle close. Applies only the layers in
  `design.yaml`'s `evolve.cycle_mode_layers` (default `[L1]`; an empty list means mine and
  record, apply nothing). That key is written for the unattended case and an unattended cycle
  never exceeds it — a 3am cycle does not rewrite the project harness with nobody watching.
  Everything outside those layers is recorded as `queued` and waits for the next attended
  close.

Refuse to run while any task or ticket is `in_progress` — same rule teardown holds, for the
same reason. Half a run is not evidence: a gate still executing has no result to mine, and
its recurrence count is a number that has not finished being wrong.

### Step 2 — Mine the run, don't read it

```bash
# close mode — the whole run is the unit of evidence
python3 <team-forge>/tools/evolve_mine.py <hub> --out docs/team-forge/<team>/evolve/

# cycle mode — this cycle only
python3 <team-forge>/tools/evolve_mine.py <hub> --out docs/team-forge/<team>/evolve/ \
  --since "$(jq -r '.current_cycle_id' <hub>/tracker/status.json)"
```

`--since` takes a cycle id — it slices from the first event naming it in `cycle_id`,
`payload.cycle_id` or `payload.cycle` — or an ISO date/timestamp, which keeps events whose `ts`
sorts at or after it. A value that resolves to neither mines everything and warns; read the
warning rather than trusting the event count.

**A cycle pass without `--since` feeds on itself.** It re-mines the full `events[]`, so every
`lesson` event this phase wrote in an earlier cycle comes back (any `payload.status` other than
`candidate` is admissible) and so does every earlier `policy_adopted` (admissible by
definition). Dedupe catches only what already reached an Active register row, so rows recorded
as `queued` or `rejected` return as fresh proposals — by cycle six the admissible list is mostly
the phase's own exhaust, and the run's actual evidence is buried under it.

Work from the emitted markdown, not the raw ledger. That is the entire point of the miner:
pulling 257 events into context to eyeball them is how a lead re-derives what a deterministic
pass already computed — and eyeballing is what mints the 79th event kind. The miner unions the
plugin's `KNOWN_EVENT_KINDS` (`tools/ledger_vocab.py`) with the team's own declared kinds
(`ledger.events` on a workflow design, `tracking.events_to_log` on a team one),
normalizes kinds, counts recurrence, pairs each `agent_blocked` with its resolution, and
attributes the budget.

Read one more thing, once, outside the loop — the agent memory the miner already collected,
under the admission bar above. Which file that is depends on the archetype. A **workflow**
forges a `<team>-lead` agent carrying `memory: project`, so
`.claude/agent-memory/<team>-lead/MEMORY.md` exists, alongside the `worker` and `advisor`
profiles' own dirs. A **team** does forge a `<team>-lead.md` file — `lead` is a roster entry
like any other — but that file carries **no `memory:` frontmatter**: the orchestrator role is
adopted by the main session at `/<team>-team`, and `forge.py` emits native memory only for
roster entries whose role is in `DISPATCHED_MEMORY_ROLES` (`advise`). So
`.claude/agent-memory/<team>-lead/` never exists on that archetype and the memory that does
is `.claude/agent-memory/<team>-<advisor-name>/MEMORY.md`. The miner globs
`.claude/agent-memory/<team>-*/MEMORY.md` either way, so work from the paths it listed under
`source.memory_dirs` rather than from a path one archetype never emits.

### Step 3 — Snapshot before you edit anything

Record `git rev-parse HEAD`, then copy `docs/team-forge/<team>/lessons.md`,
`.claude/team-forge/<team>/design.yaml`, and every file a candidate targets or its check reads
(such as `tracker/status.json`) into `docs/team-forge/<team>/evolve/snapshot-<YYYY-MM-DD>/`.

This is the rollback Step 6 restores from. Take it before the first edit, not after the first
success — a check that can fail with no way back is not a check, it is a hope.

### Step 4 — Classify each candidate

Per admissible candidate, decide **layer + target + action**
(`amend` | `add_gate` | `prune` | `open_item` | `plugin_feedback`), then dedupe against **all
three** existing tables. The miner's own `--register` dedupe only reads Active rows, so a claim
already sitting in Candidates or in the ablation queue arrives looking brand new on every pass:

- same normalized claim as an **Active** row → bump that row's evidence refs rather than opening
  `LL-n+1`. A register that carries one lesson twice is already two registers, and they start
  disagreeing at the first supersede.
- same claim as a **Candidates** row → update that C-id's seen / first-last cells, and promote
  it to Active only when *this* pass supplies the admissible signal it was waiting for. A second
  C-id for the same claim resets its sighting count to one and the row never crosses the bar.
- same claim as an **Unexercised** entry → the thing has a trace again, so reset its
  runs-without-a-trace count and mark it `watch`; do not file it as a new lesson, and do not
  leave a `prune now` standing against something this run exercised.

Then route what the dedupe left:

- Anecdotes → the **Candidates** table. Not applied, not argued with, just recorded with what
  was seen and when.
- Entries in the register with no trace in this run → the **Unexercised (ablation queue)**,
  each with a decision: `prune now` only when it has gone ≥ 2 runs without a trace **and** no
  `done_when` check names it; otherwise `watch`.
- A candidate you cannot name a check for — one that fails on the Step-3 state and passes
  after the edit (Step 6) — is not applicable yet. It goes to Candidates with "no check that
  can fail" as its reason — the same rule `team-forge:goal` holds for `done_when` versus
  `open_items`, applied to lessons.

### Step 5 — Apply, by layer

Follow `references/layers.md` — it holds the per-target procedure for each of L1's
targets (the agent memory this archetype actually has, the register, `contract.yaml`
`open_items`, and the team's gate surface — a workflow's gate scripts, a team's milestone
go/no-go criteria), L2's (`design.yaml` + `--resync`, project `.claude/rules/`, promoted
skills), and L3's plugin-feedback file.

Every applied row names its check **before** the edit is kept. A change counts as applied
only once the copy the runtime runs carries it — a workflow's `status.json.plan`, a team's
milestone `go_no_go` criteria — so its check reads that copy: a gate changed in `design.yaml`
while `plan.gates` still holds the old command is not applied. When the only route into that
copy is unsafe, such as a `--resync` that would overwrite hand-written text in a forged file,
log the row `queued` with that reason, not `applied`.

L2 lands on a branch `evolve/<team>-<YYYY-MM-DD>` for the user to approve, so until the user
approves it an L2 row is `queued`, a Candidates row (`references/register-format.md`); the
pass that finds it merged and carried by the runtime copy records it `applied`. L1 is
auto-applied once the evidence bar is met. Anything touching `.claude/agents|skills|rules` from
inside a live session goes through the `fresh_session` handoff already specified in
`team-forge:run` — the edit would otherwise race the files this session has loaded.

### Step 6 — Verify: red on the snapshot, green after

Write each check as a command whose exit code is its verdict, and run it twice: once on the
Step-3 state (the recorded HEAD, or the snapshot copies put back), where it must **fail**, and
once after the edit, where it must pass. A check that already passes on the snapshot cannot
fail, so it says nothing about the edit; neither does one whose own text says it cannot go red.
Restore that target and move the row to Candidates with "no check that can fail" as its reason.

Record every applied change to `agent_evals/<team>/evolve-<YYYY-MM-DD>/grading.json`, one
entry per change, naming its row and both runs:

```json
[{"text": "<the lesson, as applied>", "register_id": "LL-n", "passed": true,
  "before": {"command": "<the check>", "exit": 1, "output": "<what it printed on the snapshot>"},
  "after":  {"command": "<the check>", "exit": 0, "output": "<what it printed after the edit>"}}]
```

`forge.py` has created an empty `agent_evals/<team>/` for every team since the beginning and
nothing has ever written to it. This is what writes to it.

**Every new automated check also gets a negative control** — break what it watches, confirm it
goes red, restore.

A failed check restores that target from the Step 3 snapshot, demotes the row to Candidates
with the failure recorded as its evidence, and does not stop the rest of the pass.

### Step 7 — Prune (this phase is not additive)

For each `prune now` entry: delete it on the branch, re-run the project's harness and the
team's full gate set, and keep the deletion only if it stays green. The gate set lives in a
different place per archetype: a **workflow**'s is `status.json.plan.gates`, baked from
`design.yaml`'s `gates:`; a **team**'s ledger has no `plan` block at all (`--resync` returns
early on the team archetype for exactly that reason), so its equivalent is the `go_no_go`
criterion on each entry in `design.yaml`'s `milestones:`, run by hand.

If something goes red, restore, move the entry back to `watch`, and record what the deletion
broke — that failure is the observed evidence the entry was waiting for, and it belongs in the
register instead of in the head of whoever ran the ablation.

This is GOAL.md's ablation doctrine ("Prompt cleanup is ongoing maintenance, not a one-time
event: delete on a branch, run the harness + a dogfood transcript, re-add only what observed
failures demand") and it is why evolve is not a phase that only grows things. A register that
only accretes is how a prompt surface rots — every row a bet re-paid on every run, and no row
ever settled.

### Step 8 — Record

1. Log one `lesson` event per applied / rejected / queued row into `status.json.events[]`, after
   the Step-2 `mined_at` — the lint reads only events between `mined_at` and `last_run` as this
   pass's, so the run's own mid-run lessons stay out of it:

   ```json
   {"kind": "lesson", "agent": "lead", "ts": "<iso8601>", "payload": {
     "claim": "<one sentence>",
     "evidence": {"type": "recurrence|blocked_resolved|gate_failure|budget_attribution|policy_adopted|lesson_event|memory_note|anecdote",
                  "refs": ["<event id / gate / path>"]},
     "layer": "L1|L2|L3", "target": "<path#key>",
     "action": "amend|add_gate|prune|open_item|plugin_feedback",
     "status": "candidate|applied|rejected|queued", "register_id": "LL-n|C-n|null"}}
   ```

   The status must match the table its row sits in, as `references/register-format.md`
   (Admission) sets out. An `applied` event names its row and carries an admissible type with
   non-empty `refs`, never `anecdote`. To correct an event, log a new one for the same
   `register_id` — or, for one with no id, the same claim — and the later one counts; an id
   drafted and never used is logged `rejected`.

2. Stamp the pass into the ledger as a top-level `evolve` key — written **after** the `lesson`
   events above, so `last_run` is later than everything this pass wrote:

   ```json
   {"evolve": {"last_run": "<iso8601>", "mode": "close|cycle",
               "cycle": "<current_cycle_id, or null in close mode>",
               "candidates": "docs/team-forge/<team>/evolve/candidates-<YYYY-MM-DD>.json",
               "mined_at": "<that file's own mined_at, copied verbatim>",
               "unjudged": ["<LL-n applied by cycle passes since the last judged close>"],
               "rows": {"applied": 0, "queued": 0, "rejected": 0, "candidates": 0}}}
   ```

   `unjudged` carries forward what no judge has seen: a cycle pass writes the previous stamp's
   list plus every row it applied, and a close pass writes the previous list for its judge to
   cover (Step 9).

   This is the marker `team-forge:teardown` Step 1 reads, and it is the whole freshness
   contract: teardown passes when `mode` is `close`, when `mined_at` matches the `mined_at`
   inside the file `candidates` names (and no later `candidates-*.json` exists), and when no
   event in `events[]` carries a `ts` after `last_run` — that last one is what "mined from the
   final state" actually means, since work logged after the pass is work the pass never saw.
   It has to be content rather than mtimes: the miner writes the candidates file first and item
   1 above then appends to `status.json`, so a *finished* pass always leaves the ledger the
   newer file. A gate on that ordering fails on success and prescribes another evolve pass,
   which reproduces it — teardown would re-run evolve forever. Write the key even when the pass
   applied nothing; a pass that found no lessons still ran.
3. Update the register banner in `docs/team-forge/<team>/lessons.md` — forge version, date,
   cycle, events mined (`references/register-format.md`) — then lint it against this pass's
   ledger events, grading file and Step-3 snapshot. Before the judge exists, add
   `--before-judge`; Step 9 runs it again without:

   ```bash
   python3 <team-forge>/tools/evolve_mine.py --lint-register docs/team-forge/<team>/lessons.md \
     --ledger <hub>/tracker/status.json \
     --grading agent_evals/<team>/evolve-<YYYY-MM-DD>/grading.json \
     --snapshot docs/team-forge/<team>/evolve/snapshot-<YYYY-MM-DD>/lessons.md --before-judge
   ```
4. Refresh the dashboard per `team-forge:run`'s Observability section.
5. One commit, whose message names what was learned rather than the phase. A row or note may
   call a record committed only if `git ls-files` lists it; a project may ignore the miner's
   `candidates-*` files, so check first.

### Step 9 — Judge independently, then hand off

**`close` mode** does not hand off on the producer's word. Dispatch a judge that did not
produce this pass — a fresh agent, not one of the team's seats; the producer's own advisor does
not count, because the producer briefed it. Write its brief to `judge-brief.md` beside the
grading file: this skill and its references as the rubric, plus the pass's commit, the Step-3
HEAD and the snapshot folder — not the producer's verdicts or summary. The judge re-runs every
row's check on both states, every negative control, and the Step-8 lint itself, covering every
row this pass added and every row in `evolve.unjudged`, and writes its verdict beside the
grading file as `judge.json`:

```json
{"mined_at": "<the pass's evolve.mined_at>", "commit": "<sha judged>",
 "judge": "<who judged: agent type and session, never a team seat>",
 "brief": "judge-brief.md",
 "rows": [{"register_id": "LL-n", "verdict": "PASS|FAIL",
           "evidence": "<what it re-ran, what it saw>"}],
 "verdict": "PASS|FAIL"}
```

The verdict goes in that file, not the ledger: an event after `evolve.last_run` fails teardown's
freshness check. On FAIL, fix what the judge named, re-run Step 8 (which re-stamps the `evolve`
key), and have it judged again. On PASS, commit `judge.json` and its brief with the pass, then
run the Step-8 lint without `--before-judge`. `team-forge:teardown` refuses a close pass with no
committed PASS `judge.json` for its `mined_at`.

**`cycle` mode** has no judge of its own: the rows it applies wait in `evolve.unjudged` for the
next close's judge, and the pass returns to the drain loop, which owns the next cycle.

## Failure modes

- **Applying a single anecdote as a rule** → it reads as a lesson because it is vivid, and a
  one-off event kind is the most vivid thing in the ledger. One occurrence is a Candidates
  row. The bar exists because ~50 of one run's kinds fired exactly once.
- **Hand-editing a forged agent under `.claude/agents/`** → the next `--resync` silently
  reverts it, and the lesson dies without an error. Agents are regenerated from `design.yaml`;
  edit the design, run `--check`, then `--resync`.
- **Letting the register duplicate live ledger state** → task status, spend, gate results and
  progress all belong to `status.json`; the register holds judgment. Duplicating live state is
  how a memory starts lying, and a lying register is worse than none because it is checkable-
  looking.
- **Accreting forever** → skipping Step 7 turns the register into a growing prompt surface
  nobody ablates. Prune on the same pass that adds, or the queue is decorative.
- **Evolving a run whose gates never actually ran** → there is nothing to mine. The honest
  output is a register with zero new rows and a line saying the gates did not fire, not a
  table of plausible-sounding lessons reconstructed from the plan.
- **Snapshotting after the first edit** → the rollback then restores a state that already has
  the change in it, and the failed check has nowhere to go. Step 3 comes first, always.
