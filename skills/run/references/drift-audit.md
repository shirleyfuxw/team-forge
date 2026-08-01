# Drift audit — the dashboard verifier (producer ≠ verifier)

The lead is primed to see its own ledger as correct; the audit exists so the
dashboard the human reads was checked by something that ISN'T the lead. It
replaces the retired standing tracker/monitor pattern in all but one case.

## Default: a dispatched cold check

At milestone / cycle boundaries (and before the end-of-run summary), dispatch a
cold agent — the worker profile on a refute-only brief, or a plain subagent —
with exactly this brief:

1. **Pull authoritative state** (never trust the ledger's rollups): `git
   rev-parse` the integration branch for the true HEAD; the `tasks[]`/tickets +
   gate records for real progress; the `[check: …]` commands of any `done_when`
   entry the ledger claims met.
2. **Reconcile** against `status.json` (and the rendered dashboard): stale
   rollups (`head_sha`, `current_task`/`current_milestone`, `pr_url`, `budget`),
   claimed-met signals whose check doesn't actually pass, events that contradict
   task state.
3. **Report drift, don't fix it** — return the list; the lead (single ledger
   writer) corrects `status.json`, re-renders (`gen_dashboard.py`), and logs a
   `drift_corrected` event. No findings → say so explicitly.

## Exception: a standing monitor teammate

Only where nobody is watching between renders — a **recurring/unattended
workflow** (`ledger.dashboard_owner: monitor_agent`; forge enforces
recurring-only) or a persistent **team roster** that declares a monitor role.
Same procedure, continuously: pull, reconcile, rewrite the dashboard (it is the
single-writer for `dashboard.html`), and `SendMessage` the lead any drift. The
lead stays single-writer for `status.json`.
