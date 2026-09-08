# The lessons register — `docs/team-forge/<team>/lessons.md`

One file per team, in the KB (durable, human-readable, survives teardown), holding what the
team learned and what it only suspects. It is modeled on a versioned belief register whose
central insight is worth restating before the format: **the failure is not that a belief was
wrong — it is that a wrong belief was indistinguishable from a checked one.** Every column
below exists to keep those two apart.

## Canonical shape

```markdown
# <team> — lessons register

> Verified against team-forge **0.12.0** · last evolve <YYYY-MM-DD> (<cycle>) · events mined: N
> One version governs this file. Admission: a row needs evidence (recurrence >= 2,
> blocked->resolved, gate failure with root cause, budget attribution). Single anecdotes
> go to ## Candidates.

## Active

| # | Lesson | Evidence | Applied to (layer:path) | Check | Since |
|---|---|---|---|---|---|
| LL-1 | Dashboard renders inside the drain wave cost more than the wave | budget: 6 renders @ ~116k, 1010% of soft target | L2:design.yaml#ledger.dashboard_owner | `forge.py --check` clean + wave spend under target next cycle | 2026-09-08 |

## Superseded / falsified

| # | Lesson | Died at | Replaced by |
|---|---|---|---|

## Candidates (evidence pending)

| C-id | Claim | Seen | First/last |
|---|---|---|---|

## Unexercised (ablation queue)

| What | Since | Runs without a trace | Decision |
|---|---|---|---|
```

### The banner

One version stamp governs the whole file, deliberately. Per-row stamps drift apart, and a
table carrying six different versions tells you nothing about whether the table as a whole is
current. When `FORGE_VERSION` moves, you re-verify **the file** and then move the one number.
A row that cannot be re-verified moves to *Superseded / falsified* rather than sitting under a
banner it was never checked against.

`events mined: N` is the count the miner reported, not a running total — it is how a reader
tells "this run had nothing to teach" apart from "nobody ran evolve."

### Columns that carry weight

- **Evidence** — the admissible signal *and* its refs, in the form `recurrence: 4 ×
  gate_flaked` or `blocked→resolved: <agent>/<issue-key>`. Not "observed during the run".
- **Applied to** — `L1|L2|L3:<path>#<key>`. A row with no path is not applied; it belongs in
  Candidates.
- **Check** — the command or predicate that proves the lesson took effect, quoted well enough
  to re-run. A row whose check is "reviewed" is an anecdote wearing a check's clothes.
- **Since** — the date it was applied, which is what makes the ablation queue's "runs without
  a trace" countable.

### What does not go in it

Task status, spend, gate results, progress, current pointers — all of that lives in
`status.json` and is read live. The register holds judgment: what to believe, why, and what
would falsify it. Duplicating live state is how a memory starts lying, and a register that
lies is worse than no register, because it looks checkable.

## Admission

A row enters **Active** only with an admissible signal (the six in SKILL.md: recurrence ≥ 2,
`blocked_resolved`, `gate_failure` with a root cause, `budget_attribution`, `policy_adopted`,
`lesson_event`). Everything else enters **Candidates** with what was seen and when — and stays
there, at no cost, possibly forever. A candidate that recurs on a later pass is promoted by
adding an Active row; its C-id is retired in place, not deleted.

`policy_adopted` deserves its own note: a rule the lead already applied mid-run is *already in
force* and lives in no file. It is admissible by definition because the run itself is the
experiment — the only open question is where the rule gets written down.

## Ids are append-only

`LL-1`, `LL-2`, `LL-3`… never renumbered, never reused, and never re-sorted into a nicer order.
The ids are cited from `status.json.events[].payload.register_id`, from the `grading.json`
entries under `agent_evals/<team>/`, and from commit messages — renumbering silently
re-points every one of those at a different claim.

## Supersede and falsify

**Changing a row is a supersede, not an edit.** Add a new Active row with the new claim, then
move the old one to *Superseded / falsified* with what killed it and a pointer to its
replacement. Editing an Active row in place destroys the only record that the belief ever
changed, and the next reader has no way to tell a revised row from an original one.

A row moves to *Superseded / falsified* when: its check goes red and the cause is the claim
rather than the check; the ablation queue prunes it and the harness stays green; a later run
produces contradicting evidence; or the version banner moves and it cannot be re-verified.

**Keep the dead rows.** A claim that turned out to be wrong is kept, with what killed it and
what replaced it, because the reasoning that produced it is still plausible — and the next
reader, working from the same plausible reasoning and the same run artifacts, re-derives the
identical wrong belief and re-pays for it. The *Died at* column is the cheapest possible
inoculation. "Not yet replaced" is a legitimate value in the last column; leave it honest
rather than inventing a successor.

## The ablation queue

*Unexercised* holds what the register carries that this run never touched — a rule nothing
invoked, a gate nothing tripped, a lesson nothing needed. Each gets a decision:

- **`prune now`** — only when it has gone ≥ 2 runs without a trace **and** no `done_when`
  check names it. SKILL.md Step 7 deletes it on the branch, re-runs the harness and the gate
  set, and keeps the deletion only if green.
- **`watch`** — everything else, with the run count incremented.

A queue whose every entry says `watch` forever is a queue nobody is using. Prune on the same
pass that adds, or the register only grows, and a prompt surface that only grows is the exact
decay this phase exists to reverse.

## The mechanical check

```bash
python3 <team-forge>/tools/evolve_mine.py --lint-register docs/team-forge/<team>/lessons.md
```

It checks the format, not the judgment: the banner is present and parses; the four sections
exist with their expected columns; no prose line wrapped onto a `## <section>` line (the
parser switches sections on any line starting `##`, so a wrapped sentence silently reassigns
the rows after it — the forge shipped exactly that); every id is unique; every Active row
carries a non-empty Evidence, Applied-to and Check; no Active row duplicates another's
normalized claim; and every Superseded row records what killed it. Exit 0 is the register's
own gate — run it in SKILL.md Step 8, before the commit.

Two checks it deliberately does **not** make, because it is handed one file path and nothing
else: that no id was *renumbered* since the previous commit (needs git) and that every
`register_id` cited by a `lesson` event resolves to a row (needs the ledger). Both are yours
at Step 8, where both inputs are already open. Do not read a green lint as covering them —
a documented check that does not exist is indistinguishable from one that passed, which is
the failure this whole register is shaped against.
