# GOAL — the team-forge north star

*Defined 2026-08-01. Supersedes the implicit goal ("auto-generate project-specific
agent teams") in README/SCOPING. Frozen-decision style: revise via erratum, not
silent edits.*

## The product is a verified problem contract, not an agent team

team-forge exists to help the user produce **one major deliverable** per project:

1. **The problem** — what the user is *actually* trying to solve. Interrogated,
   not transcribed: the user's first phrasing is a symptom; the contract states
   the question behind it, what's out of scope, and who decides what
   (`lead_decides` / `user_decides`).
2. **The verification steps** — how the model checks, *mechanically and without
   the user present*, that the problem is solved: `done_when` conditions, gates,
   runnable acceptance checks. If a condition can't be checked by the model, it
   isn't a verification step yet — it's an open interrogation item.

Everything else this repo emits — rosters, launchers, workflow loops, tracker
files — is **optional execution machinery**, generated minimally and only when
the contract itself demands it (scale, sessions, or unattended runs that a bare
contract can't survive).

One piece of machinery is exempt from demotion: the **dashboard**, kept as the
**agent-behavior observation surface**. Verification steps are the model checking
the work; the dashboard is the human checking the model — what the agents are
doing, whether they're drifting from the contract, whether gates actually ran.
Autonomy bounded by self-verification still needs a place where the human audits
the verifier.

## Why

Model capability is no longer the bottleneck; **elicitation and verification
are**. Two consequences drive everything here:

- **Standing instructions decay silently.** Every baked instruction is a bet that
  our judgment beats the model's, re-paid on every run, and it fails without
  erroring — it just caps the model. So the prompt surface is kept at the
  *measured minimum*: content earns its place through observed failures
  (ablation), not through plausibility.
- **Autonomy is bounded by exit criteria, not by orchestration.** An agent can
  run long and hard exactly to the extent it can tell, by itself, whether it is
  done and whether it is drifting. Effort spent specifying *procedure* migrates
  into effort spent specifying the *acceptance test*.

## What this changes

- **The phase structure inverts.** Problem interrogation + verification design
  (today's Phase 1–2) *are* the product. Design/forge (Phase 3–4) become an
  optional back end, reached only when the contract needs standing machinery —
  the PR #21 "skip routes" flip from exception to default.
- **The `goal:` block (PR #26) is the center, not a stamp.** The contract —
  statement, done_when, decision split, verification steps — is the artifact the
  user approves and the model executes against; launchers merely carry a copy.
- **Skills-as-product survives, verification-first.** A `skill_gaps` entry with
  `kind: verification` and a runnable acceptance check is precisely a
  verification step made durable. Gate discovery *is* skill-gap discovery —
  that pipeline stays.
- **Prompt cleanup is ongoing maintenance, not a one-time event.** Per model
  generation: delete on a branch, run the harness + a dogfood transcript,
  re-add only what observed failures demand.
- **The dashboard reorients around the contract.** Its job is behavior
  observation: contract + done_when status, gate outcomes, agent activity and
  drift — not mirroring machinery internals. Panels earn their place by
  answering "is the model doing what the contract says, and how do we know?"

## Non-goals

- Scaffolding as the deliverable. A forged roster no one needed is negative value.
- Predefined workflows as the default. The default is: contract + existing
  skills/subagents, executed directly.
- Instructions that encode how the model should *work* rather than how the work
  is *checked*.
