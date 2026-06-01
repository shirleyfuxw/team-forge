# SCOPING.md v7 — Critical Review

**Date:** 2026-05-31
**Reviewer:** Opus 4.7 (subagent, no skin in the game)
**Verdict (lede):** **Not ready for implementation. Needs another iteration — and the resume / memory finding is large enough that a fundamental rethink of the agent-teams target is on the table.**

---

## 1. The killer finding — HERC's defining use case collides with the agent-teams primitive

The memory verification's most damaging fact is not "no per-teammate memory." It is this, from `specs/agent-teams-memory-model.md` lines 73-87, quoting official docs:

> "No session resumption with in-process teammates: /resume and /rewind do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist."

Now read the worked example. The HERC researcher agent in `/Users/shirleyfu/8888/wjsl_trader/.claude/agents/herc-researcher.md` lists, as its core triggers, "*continue multi-session research*," "*pick up where we left off*," "*run HERC research overnight*." Multi-session, resumable, multi-day research **is** the use case team-forge exists to serve, per SCOPING line 27 ("Feed it a project context and it runs a human-in-the-loop design loop"). The combiner-research stack is explicitly the "prior art" team-forge generalizes (line 40).

On resume, the entire team is gone. SCOPING line 174 claims the tracker layer "persists across cohorts" — but `status.json` persists, the tracker *agent* (which holds the aggregation logic in its context window) evaporates. Memory section row 1 also speculates about a `~/.claude/memory/<team>/<teammate-id>/` directory that the verification has refuted; the "design intent (pending verification)" table is now design intent that is verifiably wrong.

**Why it matters:** Either (a) HERC-style overnight, multi-session research cannot use this primitive at all and team-forge needs a different target (e.g. a lead-driven dispatch model that doesn't depend on persistent teammates), or (b) every forged team must be designed around an "on-resume rehydrate" protocol that re-spawns teammates from `status.json` + the hub directory before any work resumes. SCOPING acknowledges neither. The whole roster/coordination story assumes teammates that survive sessions.

**Fix candidates:**
- Add an explicit "Resume model" section: what happens when the lead is `/resume`'d? Does the team-launcher skill detect missing teammates and respawn? Is the hub directory the only durable state, with every teammate prompt explicitly told to read it on spawn?
- Reconsider whether the agent-teams primitive is the right target at all for iterative-research domains, vs. a lead-orchestrates-fresh-Agent()-dispatches model (the current HERC pattern) that doesn't depend on persistent teammates.

This is the single highest-priority issue in the document.

---

## 2. Hard contradiction — markdown OR YAML as the Phase 3 → Phase 4 contract?

SCOPING line 274 marks `design.yaml schema as source of truth` as **resolved/abandoned** in v6, replaced by the markdown design doc. Line 59 then says Phase 3 produces "a markdown design doc (`design.md`) + a structured YAML summary (`design-summary.yaml`)" and Phase 4 "Reads design doc + summary → emits `.md` files…"

But both supporting specs assume the opposite:

- `specs/workflow-integration.md` (lines 79-150) is a four-layer schema for `design.yaml` with hard validators (`WORKFLOW ELIGIBILITY`, `WORKFLOW LAUNCH CONTEXT`, `STATE INVALIDATION DECLARATION`, `COMMS CLOSURE`). Every validator reads YAML fields. None of these can run against a freeform markdown narrative.
- `specs/dynamic-per-milestone-workflow.md` line 17 ("Read milestone spec from `design.yaml` (`loop.milestones[N]`)") has the runtime orchestrator parsing `design.yaml` at milestone entry.

If markdown prose is the source of truth, how does Phase 4 deterministically emit agent `.md` files, a manifest, an evals scaffold, a launcher skill prompt, and per-milestone validators? Free-form prose is not reliably machine-parseable — the forge would have to LLM-extract the structure on every run, which means the YAML is implicitly the contract anyway, just re-derived per invocation.

This is the design that has to be made before anything is buildable: **pick one as authoritative, declare the other as derived.** SCOPING line 11 says the YAML is "valuable for user review + future reference" — that's a documentation role, not a contract role. If that's all it is, drop it; if it's the actual contract, mark it as such and move the markdown to "human-readable summary."

**Fix:** Either (a) markdown is human-only, YAML is the Phase 4 input, validators run on YAML — accept that v6's "design.yaml schema as source of truth" was correct and undo the v6 resolution; or (b) markdown is the contract, Phase 4 begins with an LLM "extract structured intent" step, and the supporting specs need rewriting. Without picking, Phase 4 cannot be specified.

---

## 3. Hard contradiction — who emits Workflow `.js`?

Three documents, three answers:

- **SCOPING line 114** + `phase3-design.herc.md` line 47: *teammates* emit tactical workflows internally for fan-out ("herc-implementer may internally use Workflow tool to fan out parallel future-leak checks").
- **`dynamic-per-milestone-workflow.md` lines 11-12:** *only the orchestrator* writes workflow `.js`, at milestone boundaries; "Implementer / analyzer / verifier agents never touch them — they are pure work agents, and giving them write-access to orchestration code would dissolve the role boundary."
- **`workflow-integration.md` lines 122-133:** the *forge* (Phase 4) emits `.js` files as part of the generation manifest, with hand-edits forbidden by `design_hash` enforcement.

These are mutually exclusive ownership models.

Worse, the SCOPING/herc-design "teammate emits and uses Workflow internally" pattern is architecturally impossible. `workflow-vs-agent-dispatch.md` line 244 and `workflow-integration.md` line 38 both confirm: `workflow()` is callable only from the main session; dispatched agents cannot launch workflows. A dispatched teammate writing and then invoking a `.js` workflow fails on the second step. The only spec that solves this (`dynamic-per-milestone-workflow.md` §7, the `WORKFLOW_READY` marker handoff) contradicts SCOPING's "teammate-emitted tactical workflows" model.

**Fix:** Resolve to one ownership model. The marker-based "orchestrator writes, main session invokes" pattern from §7 of `dynamic-per-milestone-workflow.md` is the only one that survives the launch-context constraint; commit to it and delete the teammate-internal-Workflow language from SCOPING and herc-design. If the marker handoff is too clever, fall back to "forge emits, prompted teammates only" and remove Workflow as a runtime primitive entirely.

---

## 4. Skill namespace bet creates a hard install-dependency the worked example violates

SCOPING line 162: "Forged teammates' `skills:` references look like `team-forge-brainstorming`, **not** `superpowers:brainstorming`." This means every committed `.claude/agents/<team>-*.md` in a target repo declares dependencies on the team-forge plugin namespace. Removing team-forge or running on a machine without it = forged teams stop discovering their skills. The "committed to project repo" artifacts (line 93) are no longer self-contained — they have a hidden runtime dependency on the meta-extension.

This decision then immediately contradicts the worked example. `phase3-design.herc.md` lines 39, 93-95 still reference `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:test-driven-development`, `superpowers:using-git-worktrees`, `superpowers:verification-before-completion`, `superpowers:requesting-code-review`. SCOPING line 243 calls this design doc "still mostly accurate under v7" — but on this specific decision, it isn't.

Beyond the contradiction, there's no dependency-declaration story:
- Where does the generated team-launcher skill announce its requirement?
- Does Phase 4 emit a `requires_plugins:` declaration or just trust that team-forge is installed?
- What happens when a teammate is dispatched and the `team-forge-*` skill isn't discoverable? Silent fallback? Hard error?

**Fix:** (a) Update `phase3-design.herc.md` to use `team-forge-*` everywhere, demonstrating the v7 decision; (b) add a "dependency model" subsection to SCOPING — generated teams must declare `team-forge` as a plugin dependency, the team-launcher skill must check at runtime and fail loudly if missing; (c) decide whether shared `combiner-*` agents (line 150) live in the same namespace or get their own, since SCOPING currently mixes `team-forge-*` skills with `combiner-*` agents in the same `agents/` directory.

---

## 5. HERC "phase-coverage gaps" are circular — retro-justification, not evidence

SCOPING lines 206-211 list four gaps the Phase 2.5 reviewer "would catch" in HERC's current team:

> "No tracker → status visibility relies on memory file reads
> No monitor → no user-facing dashboard
> No proactive advise agent during HYPOTHESIZE phase
> No design-review verify agent between MERGE and EXECUTE"

The first two are not gaps; they are exactly the two NEW role types v7 invented. HERC has reached a 1.547 champion across many concluded hypotheses without either. Their "absence" is a gap only if you have already mandated tracker + monitor. v7 introduces a mandatory tracker + monitor role, then points at HERC lacking them as evidence the mandate is valuable. That's circular.

The fourth (design-review verifier between MERGE and EXECUTE) is a genuine, falsifiable gap — `phase3-design.herc.md` §10 lists it as an honest open question raised by the design itself. Keep it. The first two should be dropped or honestly reframed: "v7 invents tracker + monitor; HERC currently solves these problems differently (memory-file reads + ad-hoc dashboard playground); deciding whether the v7 abstraction is worth the role-count tax is itself an open question." That's the honest version.

**Fix:** Remove "no tracker / no monitor" from the gap list, or reframe as a v7 design proposal rather than a pre-existing deficiency.

---

## 6. Tracker / monitor split looks like role-count padding

SCOPING line 74: tracker "Only talks to verifier + lead… aggregates project state." Line 75: monitor "Only reads from tracker's output + talks to tracker/lead. Updates the user-facing dashboard." Line 122: "monitor agent reads from `tracker/`, `runtime/`, and `artifacts/`, and writes the human-facing `playground/dashboard.html`."

Two ephemeral agents (verification: agent-team teammates evaporate on resume) coordinating through a `status.json` file, where one writes and the other reads. The indirection buys:
- Race-condition risk (verification §3: "No locking primitives provided")
- An extra teammate spawn + token budget on every dashboard update
- A coverage rule that demands BOTH roles even on small teams that don't need either

SCOPING line 66 says roles "may be combined in a single teammate if scope permits." If that's true, why are tracker and monitor *separate role types* in the FIXED five rather than one "observability" role with two functions? The doc invokes both motives at once: the roles are FIXED universal building blocks (line 76, "roster without all five roles is rejected") AND optionally collapsible (line 66). Pick one.

Combined with the resume problem (§1), this looks like reaching for "5 roles" — a number that feels right but doesn't survive scrutiny. The honest count is probably 3 (work, verify, advise) with observability as a *responsibility* (lead-managed `status.json` writes + a one-shot dashboard generator) rather than two new persistent role types.

**Fix:** Either collapse tracker + monitor to one "observability" role with an explicit two-function description, or justify the split with a concrete scenario where one teammate can't do both. The current text doesn't supply that scenario.

---

## 7. Phase 2.5 reviewer is currently theater

SCOPING line 58 says forge-team-reviewer "Validates the Phase 1 + 2 outputs are coherent before Design begins. Catches missing roles, ambiguous milestone boundaries, missing budget/completion data. May loop back to Phase 1 or 2 if gaps found."

Open decision #4 (line 258) admits the spec is unwritten: "What does the Phase-2.5 reviewer actually check? How does it decide to loop back to Phase 1 vs 2 vs proceed?" So the gate's content is undefined.

Worse, line 76 says roster role coverage is "rejected at Phase 3 design validation" — but Phase 2.5 (line 58) claims to "catch missing roles" before Design begins. Roster is concretized in Phase 3, not Phase 2. The reviewer therefore cannot meaningfully check role coverage; that check belongs to Phase 3 by the doc's own definition. Removing role-coverage leaves the reviewer with "ambiguous milestone boundaries" and "missing budget data" — both worth catching, but neither distinct enough from a normal `superpowers:writing-plans` post-check to warrant a dedicated phase.

**Fix:** Either (a) merge Phase 2.5 into Phase 2 as a planning-completeness checklist (cheaper, no new agent), or (b) write the reviewer's actual rubric and demonstrate at least one concrete catch — including the rule that distinguishes "loop back to 1" from "loop back to 2" from "proceed." Without that, this is process theater that adds an agent boundary and a token tax for no measurable gain.

---

## 8. "No tools_allowed" + "read-only librarian" is unenforceable

SCOPING line 124: "No `tools_allowed` declarations on teammates — they get whatever tools they need." Memory verification §3 confirms: no access control enforced by the team system; all teammates have full Read/Write/Bash.

Then SCOPING line 72 describes the advise role's librarian as read-only, and `phase3-design.herc.md` line 67 calls combiner-librarian a "Read-only memory + INDEX query agent."

If there's no tool restriction and no access control, "read-only" is a prompt suggestion the librarian agent could violate at any time without team-forge noticing. The label is aspirational, not architectural. If the librarian's read-only-ness is load-bearing — e.g. if the single-writer rule for shared memory (line 177) depends on librarian not writing — then prompt discipline is too weak a guarantee.

**Fix:** Either (a) accept "read-only" as documentation (acknowledge it explicitly) and stop relying on it as a safety property, or (b) reintroduce `tools_allowed` for roles where it matters (advise, monitor) — the v7 decision to drop tools_allowed was made before the memory verification confirmed no access control exists. The verification changes the cost/benefit.

---

## 9. "5 roles FIXED, hard rule" contradicts one-shot domains

SCOPING line 76: "roster without all five roles is rejected at Phase 3 design validation."

`phase3-design.slim.yaml` lines 84-91 acknowledge: "Many domains (frontend, one-shot CLI work) don't have a runtime loop — omit this section entirely for those." A genuine one-shot frontend build needs a worker and a verifier. It does not need a tracker (no milestones to aggregate), a monitor (nothing recurring to dashboard), or an advise role (no recurring history to query). Under the hard rule, every such team would be rejected at Phase 3.

This contradicts the doc's own escape hatch on line 66 ("Some roles may be combined in a single teammate if scope permits"). If a one-shot CLI team has the lead double as tracker/monitor/advise, that's six functions for one teammate — and the rule has lost its meaning.

**Fix:** Make the rule conditional on milestone shape — recurring-loop projects require all five, one-shot projects require work + verify + (advise OR lead-as-advise). Or downgrade the rule from "hard" to "warning" and let Phase 2.5 actually do something useful (validate role coverage matches milestone shape).

---

## 10. Bundle scope creep — combiner agents inside a generic meta-forge

SCOPING lines 149-150: the team-forge extension ships `combiner-skeptic.md` and `combiner-librarian.md` as `agents/` files in the extension itself. These agents are combiner-specific — they reference rejected-hypothesis corpora, champion configs, NLM literature. They are not generic across all forged teams.

team-forge is supposed to be a generic meta-extension for any project domain. Shipping a domain-specific toolkit inside it conflates two concerns:
- The generic forging pipeline (Phase 1-4, role types, hub layout)
- A combiner-research domain toolkit (combiner-skeptic, combiner-librarian, combiner-team skill, combiner-peer-debate skill)

This is the kitchen-sink concern the user flagged. If team-forge installs into a non-quant repo (say, a frontend project), it ships four combiner-specific files that have zero use there. And if combiner-research evolves separately (new debate patterns, new librarian fields), every team-forge release ships those changes even to teams that don't use them.

**Fix:** Split into two extensions. `team-forge` ships the generic forging machinery + shared skills (brainstorming, writing-plans, design, forge, tracker, monitor). `combiner-toolkit` (or similar) ships combiner-specific agents + the combiner-team and combiner-peer-debate skills. Forged combiner-research teams depend on both. This is the standard "core + plugin" split and it makes the dependency graph honest.

---

## What holds (calibration)

Not everything is broken. The following are sound and should survive iteration:

1. **The layered model (baked-in / human-declared / forge-reasoned), lines 78-88.** This is the clearest framing in the doc. It answers a real question ("who decides each thing?") with three crisp tiers, and the test ("anything not fitting is over-spec'd") is genuinely useful. Keep it.

2. **"Validation via agents, not hooks" as a philosophy, lines 179-192.** Defensible — hooks are out-of-band, easy to forget, hard to test. Verifier agents are first-class team members, easy to invoke, easy to evaluate. The philosophy is consistent; the failures are in execution (tracker/monitor as separate roles, line 190's "implicit at runtime" coverage check that depends on the broken assumption teammates persist across resume).

3. **The single-writer rule for shared team memory (line 177).** Inherited from HERC's existing pattern and validated by the memory verification's race-condition warning. If shared state lives in files and there's no locking primitive, single-writer is the only safe design. Keep it explicit.

4. **Two-section design output (markdown for humans, structured for machines), in principle.** The instinct to produce both a human-readable narrative and a machine-actionable spec is correct. The problem is contract ambiguity (§2 above), not that both exist. Fix the contract, keep both formats.

---

## Final assessment

**v7 is not ready for implementation.** Two of the issues above (resume model, design-doc-vs-YAML-as-contract) are buildability blockers: until they're resolved, Phase 4 cannot be specified, and the forged teams cannot reliably operate. Four others (workflow-emission ownership, skill-namespace dependency, theater Phase 2.5, tracker/monitor split) need design decisions before any code is written. The remainder are sharpenings that could land during implementation.

Ten open decisions in the doc (line 253-264), plus the resume contradiction, plus the markdown-vs-YAML ambiguity, mean the next iteration should be a v8 that:

1. Picks a stance on multi-session resume — either redesign around it or document the limitation honestly.
2. Names markdown OR YAML as the Phase 3 → Phase 4 contract and demotes the other.
3. Resolves Workflow emission ownership to one model.
4. Splits combiner toolkit out of the generic forge.
5. Either collapses tracker + monitor or justifies the split.
6. Specifies (or merges away) Phase 2.5.

The bones — agent-teams as a target, role-based coverage, design-as-doc, the layered model — are workable. The execution has accumulated v1-through-v7 cruft, and the memory verification changes assumptions further upstream than the v7 sharpenings reach. One more pass focused on the items above gets this to a buildable v8.

The risk of *another* incoherent iteration is real: this is the seventh version, and items resolved in earlier versions (YAML as source of truth, branch from Superpowers) keep getting un-resolved and re-resolved. v8 should be the version where assumptions are *frozen* — make the hard calls, document the trade-offs, and stop revisiting.
