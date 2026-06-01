# team-forge × Workflow tool integration

## TL;DR

**Recommendation: selectively integrate.**

Workflow is the right tool for a narrow, well-defined sub-class of forge output: contiguous, gate-free, fan-out-heavy runtime phases. Outside that sub-class — anywhere a human gate, an always-on agent, a peer-visible mailbox, or state.md-dependent routing lives — Workflow is structurally incompatible with team-forge's product contract.

Concretely:

- **Forge phases (Understand, Decompose, Design):** stay prompted. Three of three are gated on human approval per `SCOPING.md`. Constraint #2 (no human-input primitive) is a hard wall.
- **Forge phase Forge (file emission):** workflow-eligible — single workflow, validation pipeline → parallel emitter agents → manifest writer. Only the *main session* can launch it.
- **Runtime loop:** three phases (`pre-consult`, `dispatch`, `analyze`) are clean Workflow fits. Two (`merge`, `smoke`) are moderate — useful if Workflow already owns the adjacent phase. Four (`debate`, `execute`, `persist`, `decide`) stay prompted. `decide` is the canonical anti-pattern.

The forge should compile workflows only where design.yaml explicitly declares `orchestration: workflow` on a phase that passes a static eligibility check. Everywhere else, the emitted artifact remains a prompted `.md` agent file.

---

## Recommendation

**selectively integrate**, gated by a new `orchestration: workflow|prompted` field on each phase in design.yaml. The forge's existing validators are extended to refuse `orchestration: workflow` on any phase that:

1. carries a human gate (`human_gate`, `go_no_go`, `guided_pause`), OR
2. contains an always-on agent in `coverage`, OR
3. uses a peer-visible channel, OR
4. branches on state.md content rather than handoff-schema fields.

The first integration target is the runtime sub-sequence `merge → smoke → execute` — three contiguous gate-free phases in the HERC reference team. This is small enough to ship as a forge feature behind a flag, big enough to validate the emission pipeline end-to-end, and structurally analogous to the kind of sub-sequence other team-forge users will most often request.

---

## Integration targets

Each entry is a phase that the forge MAY emit as a `.js` workflow when the design.yaml declares `orchestration: workflow` and the static eligibility check passes.

### Forge-time

- **Forge (phase 4 — file emission).** **Rationale:** No human gate (design.yaml was approved at the end of phase 3). Output is deterministic: roster × file-templates → `.md` / `evals.json` / `SKILL.md` files. Parallelism over emitter agents is a natural fan-out (typical roster is 6–8 agents × 3–4 files). Validation is a clean pipeline gate. **Shape:** ONE workflow — validation pipeline → `parallel()` emitters → manifest writer. NOT many workflows; constraint #1 forbids nested `workflow()`. **Forced agent boundary:** file emission MUST happen inside `agent()` calls (constraint #3: JS body has no fs). **Critical:** the forge entry point must be invokable from the main session; if `team-forge-lead` is itself a dispatched agent, it cannot launch this workflow — that has to be a documented requirement.

### Runtime — strong fits

- **`pre-consult`.** **Rationale:** 3 fresh lens analysts (correctness / statistical / literature) run independently against the same `selected_threads` — textbook embarrassingly parallel fan-out. 1 round only, no revise loop. Within-round peer-flag step is recoverable in the collector agent. Maps cleanly to `parallel(analyst_a, analyst_b, analyst_c)` → merge agent.
- **`dispatch`.** **Rationale:** One implementer per selected thread, schema-validated handoff YAML, peak concurrency well under the 16-agent cap. Handoff schema validation (required-field check) is deterministic routing that the workflow JS can own — threads with incomplete handoffs are excluded from MERGE without judgment.
- **`analyze`.** **Rationale:** Structurally identical to `pre-consult` — 3 lens analysts on `cohort_results`. The conditional R2 reconciliation round is a branch on first-round structured verdict fields (not a judgment), expressible as `parallel()` → conditional `pipeline()`.

### Runtime — moderate fits (emit only if adjacent phase is already workflow)

- **`merge`.** **Rationale:** `champion_source` decision tree is fully deterministic and JS-codeable from DISPATCH handoffs. No parallelism — sequential by nature. Worth emitting *only if* DISPATCH is already a workflow, so the routing logic stays in JS rather than being lifted into a prompt.
- **`smoke`.** **Rationale:** Pure conditional gate (`smoke_required` skip-path) + 2×2 action table on verdict × champion_source. All threshold-based. Single agent call — no fan-out. Worth emitting *only if* MERGE is already a workflow, so the skip-gate is enforced deterministically.

---

## What stays in prompt

### Forge-time — all prompted

- **Understand (phase 1).** Anti-pattern. The phase IS the human clarification loop. No fan-out, no determinism. Belongs entirely in prompted `Agent()` orchestration.
- **Decompose (phase 2).** Weak. Milestone draft is judgment-driven; phase exits on go/no-go gate. A workflow could pre-draft milestones in parallel but the exit gate kills any pure-workflow shape. Prompted `Agent()` that drafts, surfaces, waits.
- **Design (phase 3).** Weak. Roster / coverage / comms design is judgment-driven, exit is a human review gate. The three hard validation rules at end-of-phase ARE deterministic but a single cheap check is not worth a workflow.

### Runtime — prompted

- **`debate`.** Hybrid. Round structure (`pipeline(propose → skeptic → rebut → mark)`) is workflow-expressible, but two structural blockers: (1) within-round implementer-to-implementer peer visibility is an async read-write-all mailbox — peer-visible channels cannot exist in a `.js` body (no fs, constraint #3); (2) lead arbitration after the skeptic marks is a judgment call, not a threshold. Keep `combiner-peer-debate` skill + lead orchestrating; workflow could at best scaffold the round structure, which is not worth the dual-maintenance cost.
- **`execute`.** Weak. One long-running remote job (30–60 min screen + done-file). No fan-out. Async wait + done-file detection are incompatible with JS body (no fs, no clock). Workflow contribution would be `agent()` wrapper only — no different from prompted orchestration.
- **`persist`.** Weak despite sequential determinism. Two anti-patterns: (1) non-idempotent appends to `MEMORY.md`, `research-journal.md`, `INDEX.md` — workflow journal resume (constraint #4) would double-write on mid-phase failure; the existing `persist.py` rotation script is idempotent on compaction only, not on append; (2) `champion_cache.yaml` update depends on `champion_source` resolved from multi-file state read, which requires agent judgment. Plus the PR creation step requires the review-receipt gate (project policy).
- **`decide`.** **Anti-pattern.** Champion candidate verdict requires "PAUSE for user" — the canonical human gate. Constraint #2 is a hard wall. The threshold classification sub-step is deterministic but because one branch is human-gated, the phase as a whole cannot run unattended. This is exactly what the Workflow constraint list is designed to flag.
- **`select`** (not in the 9 phases analyzed but called out by the runtime analyst). Human-gated in guided mode — shares the `decide` verdict.

---

## Spec changes to design.yaml

The forge needs the following schema extensions to statically enforce workflow eligibility and emit `.js` files alongside the existing `.md` outputs. All four team-forge layers are touched.

### Layer 1 — workflow

Per-phase declaration of orchestration mode and resource budget.

```yaml
loop:
  phases: [pre-consult, dispatch, debate, merge, smoke, execute, analyze, persist, decide]
  iteration_unit: cohort
  max_iterations_per_thread: 3

  # NEW: per-phase workflow eligibility block
  phase_orchestration:
    pre-consult:
      orchestration: workflow      # enum: workflow | prompted (default: prompted)
      token_budget_k: 60           # mandatory when orchestration: workflow
      max_concurrency: 3           # capped at min(16, cores-2) at emission time
    dispatch:
      orchestration: workflow
      token_budget_k: 120
      max_concurrency: 8
    debate:
      orchestration: prompted      # peer-visible channel + lead arbitration
    merge:
      orchestration: workflow
      token_budget_k: 30
      max_concurrency: 1
    smoke:
      orchestration: workflow
      token_budget_k: 25
      max_concurrency: 1
    execute:
      orchestration: prompted      # long-running async, no fs/clock in JS
    analyze:
      orchestration: workflow
      token_budget_k: 60
      max_concurrency: 3
    persist:
      orchestration: prompted      # non-idempotent appends + journal hazard
    decide:
      orchestration: prompted      # human gate
```

### Layer 2 — yaml-sections

Two additions and one extension.

```yaml
# NEW: a top-level workflow_scripts manifest (output of phase 4)
forge:
  generate:
    workflow_scripts:
      - phase: pre-consult
        path: .claude/workflows/herc-pre-consult.js
      - phase: dispatch
        path: .claude/workflows/herc-dispatch.js
      - phase: merge_smoke
        path: .claude/workflows/herc-merge-smoke.js   # contiguous sub-sequence
      - phase: analyze
        path: .claude/workflows/herc-analyze.js

# EXTEND: comms.channels gains a workflow_internal type
comms:
  channels:
    - id: pre-consult-fanout
      type: workflow_internal        # NEW enum value
      participants: [herc-correctness-analyst, herc-statistical-analyst, herc-literature-analyst]
      owning_workflow: .claude/workflows/herc-pre-consult.js

# NEW: invalidation keys — state.md fields that flush workflow journal
state:
  authoritative_store: state.md
  invalidation_keys:
    - probation.active
    - backlog
    - champion.config_path
```

### Layer 3 — per-entry shapes

Three new optional fields on roster entries.

```yaml
roster:
  - name: herc-researcher
    role: work
    inherits_main_session: true         # EXISTING — now load-bearing for workflow launch
    can_launch_workflows: true          # NEW — must be true to call workflow()
    # ...
  - name: herc-skeptic
    dispatch: always-on                  # EXISTING — now disqualifies phases from workflow
    excludes_workflow_phases: [debate]   # NEW — derived from dispatch + channels, surfaced for clarity
```

### Layer 4 — validation rules

Three new hard rules, one existing rule extended.

- **NEW: WORKFLOW ELIGIBILITY.** A phase with `orchestration: workflow` MUST satisfy all of:
  - no roster entry active in that phase has `dispatch: always-on`,
  - no channel touching that phase has `type: peer-visible`,
  - no roster entry's coverage marks that phase as `human_gate: true`,
  - `token_budget_k` is declared,
  - the phase does NOT branch on state.md content (declared via `requires_state_read: false`).
- **NEW: WORKFLOW LAUNCH CONTEXT.** Any roster entry that the forge wires as a workflow caller MUST have `inherits_main_session: true` AND `can_launch_workflows: true`. The forge refuses to emit a workflow whose only invoker is a dispatched agent.
- **NEW: STATE INVALIDATION DECLARATION.** If any phase is `orchestration: workflow`, `state.invalidation_keys` MUST be declared; emitted `.js` flushes the journal on key change.
- **EXTEND: COMMS CLOSURE.** Workflow-emitted `agent()` calls count as a `workflow_internal` channel. The validator enumerates `agent()` calls in emitted `.js` and reconciles them against roster entries; any unmatched `agent()` is a hard error.

### Manifest

`manifest.json` gains:

```json
{
  "files": [
    { "path": ".claude/agents/herc-researcher.md", "kind": "agent_md" },
    { "path": ".claude/workflows/herc-pre-consult.js", "kind": "workflow_js" }
  ],
  "design_hash": "sha256:...",
  "forge_version": "0.2"
}
```

`kind: workflow_js` is a new enum value. The CI drift check (`design_hash` ↔ `sha256(design.yaml)`) becomes load-bearing — hand-edits to `.js` are forbidden.

---

## Risks

1. **Dual state-model desync (high).** `state.md` is the authoritative store; Workflow's journal is an opaque agent-call cache. Mid-session edits to `state.md` (probation lift, backlog edit) will cache-hit on stale agent calls and bypass the change. Mitigation: workflows MUST read `state.md` through a dedicated state-reader agent at every phase entry, never cache the read; declared `state.invalidation_keys` flush the journal when changed. Carry this risk forward — it is the one most likely to produce a silent correctness failure.

2. **Comms-closure validator blind spot (high).** Forge's COMMS CLOSURE rule reasons over declared channels. Inline `agent()` calls inside emitted `.js` are a new channel type the current validator does not model — either every workflow phase fires a false closure violation, or the validator silently skips workflow internals, creating exactly the kind of gap the safety net is designed to catch. Mitigated only by Layer-2 schema extension + Layer-4 rule update above — until both ship, no workflow emission.

3. **Dual orchestration maintenance burden (medium).** The cohort loop currently lives as prose in `herc-researcher.md`. After emission, the gate-free sub-sequences live ALSO in `.js`. Any change to step ordering / retry / exit conditions must be applied to both. Mitigation: forge regeneration from `design.yaml` is the only write path for `.js`; CI checks `design_hash` matches `sha256(design.yaml)` before any workflow run.

4. **Nested-workflow incompatibility with documented parallel-researcher pattern (medium).** `herc-researcher.md` documents launching two researchers in parallel. If the researcher is a workflow caller, the second instance hits the nested-workflow constraint with no in-band signal at forge time. Mitigation: forge detects `can_launch_workflows: true` on a roster entry and refuses to also mark that entry as parallel-spawnable; surfaces this as a phase-3 design decision.

5. **Debugging story is unbuilt (medium).** Generated `.js` is code the user did not author. Workflow failures surface as runtime errors against generated line numbers. The team currently debugs via `state.md` inspection + per-agent transcripts; neither applies to compiled workflow internals. Mitigation: each workflow emits an `audit_agent()` at every phase boundary that writes a one-line status (via an agent, since the JS has no fs); forge templates emit structured comments mapping `agent()` calls back to `design.yaml` phase + roster entry; documented debugging recipe is "diff state.md pre/post + read the relevant agent's transcript".

---

## Next steps

1. **Land the Layer-2 + Layer-4 schema changes first (no emission yet).** Add `phase_orchestration`, `workflow_internal` channel type, `state.invalidation_keys`, and the WORKFLOW ELIGIBILITY / WORKFLOW LAUNCH CONTEXT / extended COMMS CLOSURE validators to the phase-3 template and the forge validator. Verify against the existing HERC reference design — every runtime phase should classify itself correctly (3 workflow, 2 workflow-if-adjacent, 4 prompted). No `.js` is emitted yet; this is a schema-and-validator-only change so the forge can statically reject misuse before any code generation lands.
2. **Prototype emission for the merge-smoke sub-sequence.** Choose the smallest contiguous gate-free sub-sequence (`merge → smoke`) as the first workflow emission target. Build the `workflow.js.j2` template, wire the manifest `kind: workflow_js`, and forge a single `.js` against the HERC design.yaml. Verify: emitted file passes workflow runtime validation; channel enumeration reconciles cleanly; `design_hash` round-trip works. This is the smallest end-to-end slice that exercises every load-bearing piece.
3. **Resolve the launch-context question explicitly.** Before expanding emission to `pre-consult` / `dispatch` / `analyze`, decide and document: does the forge ever emit a workflow that the team's lead (a dispatched agent) is expected to launch? If yes, the architecture needs a main-session shim. If no, document that workflows are only invoked from the user's main session, and add this constraint to the team-forge `SCOPING.md` so users do not design themselves into the nested-workflow trap.

---

## Appendix A — Forge phases

Per-phase verdict against the Workflow tool.

| Phase | Fitness | Deterministic | Parallelizable | Human gate | Verdict |
|---|---|---|---|---|---|
| Understand | anti-pattern | no | no | yes | prompted only |
| Decompose | weak | no | no | yes | prompted only |
| Design | weak | no | no | yes | prompted only |
| Forge | strong | yes | yes | no | **single workflow**: validation pipeline → parallel emitters → manifest writer |

Forge-phase specifics:

- **Understand.** SCOPING.md places a human gate here — clarifying questions, intent exploration, stop-and-wait. Workflow constraint #2 (no human-input primitive) makes this unrunnable as a workflow. Output is a 1-paragraph goal statement — judgment-derived. Belongs entirely in prompted Agent().
- **Decompose.** Milestone decomposition needs human go/no-go on the milestone list. Workflow cannot pause mid-run. Weak rather than anti-pattern because a workflow could pre-draft milestones in parallel before presenting — but the human gate at exit kills the pure-workflow shape.
- **Design.** Produces design.yaml and ends with explicit human review gate. The three hard validation rules (role / phase / comms closure) at end-of-phase ARE deterministic and could be a workflow sub-script, but it is a single cheap check — not a reason to rate above weak.
- **Forge.** Cleanest workflow fit with two structural constraints:
  - **Shape.** No human gate; output is deterministic file set from approved design.yaml.
  - **Structure.** ONE workflow, not many — constraint #1 forbids nested `workflow()` from agents.
  - **Forced agent boundary.** Constraint #3 (JS body has no fs/Node) means file emission must happen inside `agent()` calls.
  - **Concurrency.** 1000-agent cap and 16-concurrency cap are non-binding for typical roster (6–8 × 3–4).
  - **Idempotency note.** Workflow journal resume (#4) and manifest+design_hash idempotency are two independent mechanisms on the same surface — pick one as canonical to avoid conflicting skip logic.
  - **Launch context (critical).** `workflow()` is callable only from main session. If team-forge lead is dispatched, it cannot launch the Forge workflow. Must be an explicit design decision.

---

## Appendix B — Runtime loop

Per-phase verdict for the HERC reference team's 9-phase cohort loop.

| Phase | Fitness | Det | Par | Gate | Verdict |
|---|---|---|---|---|---|
| pre-consult | strong | no | yes | no | workflow |
| dispatch | strong | no | yes | no | workflow |
| debate | moderate | no | yes | no | prompted (peer-visible mailbox + lead arbitration) |
| merge | moderate | yes | no | no | workflow if adjacent |
| smoke | moderate | yes | no | no | workflow if adjacent |
| execute | weak | yes | no | no | prompted (async wait incompatible with JS body) |
| analyze | strong | no | yes | no | workflow |
| persist | weak | yes | no | no | prompted (non-idempotent appends + journal hazard) |
| decide | anti-pattern | no | no | yes | prompted only |

Detail per phase:

- **pre-consult.** 3 lens analysts independent against same `selected_threads`. `parallel(a, b, c)` → merge agent. 1 round only. Peer-flag step recoverable in collector. Pure deterministic fan-out shape.
- **dispatch.** One implementer per selected thread. Schema-validated handoff YAML. Peak concurrency under the 16-cap. Handoff validation (required-field check) is deterministic routing the JS can own.
- **debate.** 2-round adversarial exchange. `pipeline(parallel(propose) → skeptic → parallel(rebut) → mark)` captures round structure and `debate_rounds=2` cap. Does NOT capture: (1) within-round peer-visible mailbox (async read-write-all); (2) lead arbitration judgment after mark. Skill+lead must remain.
- **merge.** `champion_source` decision tree deterministic and JS-codeable. No parallelism — sequential by nature. Adds deterministic routing but no fan-out speedup.
- **smoke.** Deterministic gate: skip if `smoke_required=false` else dispatch tester and branch on 2×2 verdict × champion_source. All threshold-based. Single agent call.
- **execute.** One long-running remote job (30–60 min screen + done-file). No fan-out. Async wait incompatible with JS body (no fs, no clock). Log-tail and EXPERIMENT_OUTPUT_DIR extraction need agent judgment.
- **analyze.** Structurally identical to pre-consult. Conditional R2 reconciliation on verdict disagreement is a branch on structured fields, not judgment.
- **persist.** Two anti-patterns: (1) non-idempotent appends (`MEMORY.md`, `research-journal.md`, `INDEX.md`) — journal resume double-writes; (2) `champion_cache.yaml` update needs multi-file state read with judgment. Plus review-receipt gate on PR.
- **decide.** Mandatory human pause on Champion candidate verdict. Constraint #2 hard wall. Threshold classification sub-step is deterministic but one branch is human-gated, so the phase cannot run unattended. Canonical anti-pattern.

Meta-precondition: `workflow()` callable only from main session — works for the HERC researcher because `inherits_main_session: true`; a nested-agent orchestrator cannot call it.

---

## Appendix C — Cost dimensions

Ten integration costs from the cost analysis, in severity order.

### High

- **Human-gate incompatibility.** Workflow constraint #2 collides with team-forge's product contract. Every milestone in phase3-design.yaml has `go_no_go`; HERC researcher pauses for user at SELECT and PERSIST. Gates are why team-forge exists. **Mitigation:** restrict workflow compilation to contiguous gate-free runs (e.g. `merge → smoke → execute`); forge validator refuses `orchestration: workflow` on any phase with `human_gate` / `guided_gate` / `probationary_pause`.
- **Comms-closure validator blind spot.** Forge's COMMS CLOSURE rule reasons over declared channels; inline `agent()` calls in emitted `.js` are a new channel type. False violations OR silent gaps. **Mitigation:** add `workflow_internal` channel type; validator enumerates `agent()` calls in `.js` and reconciles against roster.
- **Dual state-model desync.** `state.md` (frontmatter, MEMORY.md, manifest.json) vs Workflow's resume-journal (agent-call hashes). Mid-session edits to `state.md` cache-hit on stale calls. **Mitigation:** `state.md` is sole source of truth; forged `.js` reads `state.md` via dedicated reader agent at every phase entry; `state_invalidation_keys` flushes journal on change.
- **Always-on and peer-visible agent incompatibility.** `combiner-skeptic` is `dispatch: always-on` and participates in peer-visible `debate_mailbox`. Workflow has no persistent peer; no fs in JS. **Mitigation:** DEBATE and (transitively) PRE-CONSULT-via-debate-skill stay prompted; forge excludes phases with always-on agents or peer-visible channels from workflow emission.

### Medium

- **Dual orchestration maintenance burden.** Cohort loop lives in `.md` and (after emission) in `.js`. Zero `.claude/workflows/*.js` precedent in repo. Forge template directory must carry `workflow.js.j2` alongside `agent.md.j2`. **Mitigation:** `.js` is the execution artifact, `.md` is documentation; forge regeneration is the only write path for `.js`; CI checks `design_hash` ↔ `sha256(design.yaml)`.
- **New required fields in design.yaml.** Per-phase `orchestration`, `token_budget_k` (hard ceiling, must be declared up front — silent fail mid-run if under-budgeted), `max_concurrency` (16-cap), `workflow_script_paths`, `phase_to_workflow_mapping`, manifest `kind: workflow_js`. **Mitigation:** ship as schema PR before any emission; validator hard-errors on `orchestration: workflow` without `token_budget_k`.
- **Workflow JS debugging story.** Generated `.js` is code the user did not author. No fs in JS = no diagnostic log writes. Errors surface against generated line numbers. **Mitigation:** each workflow emits `audit_agent()` at phase boundaries writing one-line status via an agent; forge templates emit structured comments mapping `agent()` calls back to phase + roster entry; documented debugging recipe is state.md diff + agent transcript review.
- **Parallel subagent + orchestrator-as-subagent incompatibility.** Constraint #1: only main session can call `workflow()`; nested throws. HERC has documented "two researchers in parallel" pattern. If researcher is workflow-compiled, second instance breaks. **Mitigation:** forge detects `inherits_main_session: true` + orchestrator role and refuses to emit workflow for that agent (or flags the parallel-spawn constraint).
- **No-fs constraint breaks in-workflow state reads.** Forged `.js` cannot read `state.md` to make routing decisions. All state-dependent branching must be hoisted into `agent()` return values — latency + token cost. **Mitigation:** restrict workflow scripts to phases with no state-dependent routing; natural complement to the human-gate restriction.

### Low

- **Role-coverage validation rule impact.** Forge requires every roster entry to have `role: work | verify | advise`. Workflow scripts add a new execution unit (`.js` as coordinator) with no role. If a forged workflow dispatches three agents but short-circuits one on fast path, coverage matrix may falsely count it as covered. **Mitigation:** role coverage validates `design.yaml` declarations only, not generated `.js` runtime behavior; `workflow_internal` channels count toward coverage only if roster's `active_phases` includes the phase.
