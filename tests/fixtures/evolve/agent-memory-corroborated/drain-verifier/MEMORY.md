# drain-verifier memory

Fixture for the miner's SECOND memory admission rule: a note written in exactly ONE cycle
section, which the ledger independently proves. The repeat rule cannot admit it — it has
been written once — so if this note comes back an anecdote, the corroboration branch is
dead code again. Mine it with:

    --memory-dir tests/fixtures/evolve/agent-memory-corroborated

against ledger-signals.json, whose three `verifier_prompt_contamination` events and
committed `lesson` event carry the same claim.

## Cycle-2026-09-01-001 — COMPLETED

### Operational learnings
- The verify brief must be built from the diff, never from the lead's summary; the verifier agrees with whatever conclusion it is handed.
- Re-reading the PR description before the diff cost about ten minutes per ticket and changed no verdict.
