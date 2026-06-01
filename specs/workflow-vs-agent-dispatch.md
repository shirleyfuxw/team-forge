# Workflow vs Prompted Agent Dispatch: Decision Framework for team-forge

**Status**: Research Report  
**Date**: 2026-05-31  
**Scope**: Official Anthropic guidance on when to use Claude Code Dynamic Workflows vs prompted Agent() dispatch for orchestrating multi-step, parallel agent systems.

---

## Executive Summary

This report synthesizes official Anthropic documentation, recent blog posts, and community patterns to answer: **when should a meta-extension like `team-forge` generate JavaScript Workflow scripts vs Python/JS agents that programmatically call `Agent()` / `SendMessage()` to coordinate subagents?**

**Bottom line**: Workflows are deterministic orchestration scripts for large, verifiable, repeatable tasks. Prompted agent dispatch (current HERC pattern) is for human-driven, interactive, multi-turn coordination where Claude decides the next step turn-by-turn. Anthropic explicitly distinguishes these patterns:

| **Dimension** | **Prompted Agent Dispatch** | **Dynamic Workflow** |
|---|---|---|
| **Who decides next step?** | Claude, turn by turn | The script |
| **Scale** | A few delegated tasks per turn | Dozens to hundreds of agents per run |
| **Repeatable artifact** | The agent definition | The orchestration script itself |
| **Context for results** | Lives in Claude's context window | Lives in script variables |
| **Interruption recovery** | Restart the turn | Resume within the same session (cache completed work) |
| **Token economics** | Lower per-task (fewer parallel agents) | Higher (many parallel agents, verification loops) |
| **Visibility** | Interactive, human-in-the-loop by design | Background execution, `/workflows` view for progress |
| **Human-in-the-loop** | Native: pause at turn boundaries | Require workarounds (run each stage as separate workflow) |

**HERC's current design** (orchestrator agent + 3 parallel subagents per phase) is best served by **prompted dispatch** because:
1. **Interactive research**: Researcher must decide which hypotheses to explore next (Phase B steps SELECT → PRE-CONSULT → DISPATCH involve human/team input).
2. **Debate-phase human gates**: The peer-debate skill requires SendMessage() for mailbox coordination and can't be deterministically scripted in advance.
3. **No large-scale parallelism**: HERC fan-out is typically 3–5 agents (analyzers/implementers), not 50+. Workflows shine at 50–1000.
4. **Token economics**: HERC's specialized, tightly-scoped pre/post phases are cheaper via dispatch than via workflow verification loops.

However, **hybrid patterns exist** for specific phases (e.g., SMOKE step as a deterministic 1-agent workflow, if reproducibility matters more than interactivity), documented in Section 5.

---

## 1. Official Decision Framework

### 1.1 Anthropic's Core Distinction

From [**Orchestrate subagents at scale with dynamic workflows**](https://code.claude.com/docs/en/workflows):

> A workflow moves the plan into code. With subagents and skills, Claude is the orchestrator: it decides turn by turn what to spawn next, and every result lands in Claude's context. A workflow script holds the loop, the branching, and the intermediate results itself, so Claude's context holds only the final answer.

**Key insight**: Workflows are not a mode of agent execution—they're a *different problem*. Use Workflows when:
- The task is too large for one context window
- The split strategy is *known in advance* (not decided by Claude mid-task)
- Result quality (via verification/adversarial review) matters more than token cost

**Key insight from the table** ([official docs](https://code.claude.com/docs/en/workflows#when-to-use-a-workflow)):

| **Criterion** | **Subagents / Skills** | **Workflows** |
|---|---|---|
| Scale | A few delegated tasks per turn | Dozens to hundreds of agents per run |
| What's repeatable | The worker definition | The orchestration itself |
| Where intermediate results live | Claude's context window | Script variables |

### 1.2 Official Use Cases

**Use Workflows for** ([from blog announcement](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code)):
- **Codebase-wide bug hunts** with independent verification (spawn 50 agents, each checks a module, then synthesize)
- **Migrations spanning thousands of files** (deterministic fan-out, no interactivity needed)
- **Security audits across entire services** (repeatable quality pattern with adversarial verification)
- **Cross-checked research** where you want agents to independently attempt the problem, then vote on claims

**Use Prompted Agent Dispatch for**:
- **Interactive research** (user/orchestrator decides next hypothesis mid-loop)
- **Tight feedback loops** (human feedback between phases)
- **Specialized subagent orchestration** (3–5 parallel workers, tightly coordinated)
- **Persistent context** (results need to live in the orchestrator's conversation, not a script variable)

---

## 2. Decision Criteria Deep Dive

### 2.1 Determinism & Control Flow

**Workflow**: The orchestration is deterministic JavaScript. You own the loops, branching, and fan-out structure before any agent runs. Useful when the shape is known in advance.

```javascript
// Workflow: Shape is fixed at script creation
const results = [];
for (const alpha of alphas) {
  results.push(await agent("analyzer", { alpha }));
}
const verdict = await agent("synthesizer", { results });
```

**Prompted Dispatch**: Claude decides, mid-conversation, whether to spawn a next subagent, what prompt to give it, and how to interpret results.

```python
# Dispatch: Shape emerges from Claude's reasoning
# System prompt says: "If pre-consult score > threshold, dispatch implementer; else select new hypothesis"
# Claude reads the score and decides dynamically.
```

**HERC relevance**: HERC's Phase B (8-step cohort loop: SELECT → PRE-CONSULT → DISPATCH → MERGE → SMOKE → EXECUTE → ANALYZE → PERSIST → DECIDE) has *conditional branching* at DECIDE (is champion beaten? do we continue?). This is better suited to prompted dispatch because **Claude needs to interpret live backtest results and decide the next hypothesis theme**, not follow a pre-scripted path.

**Verdict for team-forge**: Unless the user describes an *entirely deterministic, known-in-advance* pipeline, default to **prompted dispatch**. Workflows are for "run the same shape 100 times with different inputs"; dispatch is for "each iteration shapes the next."

---

### 2.2 Resume / Idempotence

**Workflow Resume (official)** ([code.claude.com/docs/en/workflows](https://code.claude.com/docs/en/workflows#resume-after-a-pause)):

> If you stop a run, you can resume it: agents that already completed return their cached results, and the rest run live. Resume works within the same Claude Code session.

- **Critical limitation**: Resume is session-scoped. If you exit Claude Code while a workflow is running, the next session starts the workflow fresh.
- **What it buys**: A long-running parallel sweep (100 agents, 30 min wall time) that hits a pause: completed agents cache their results, remaining agents pick up where they left off. No wasted re-work.
- **Idempotence**: Workflow runner internally prevents duplicate execution of agents that already returned results.

**Prompted Dispatch Resume**: 
- Agent sessions can be resumed via `Agent SDK` or `claude --resume session_id`, but the semantics are different: you're returning to the same conversation context, not skipping completed work.
- If the orchestrator agent is interrupted, re-prompting it will likely re-dispatch all subagents (no intelligent cache).
- Better suited to workflows where each phase is relatively quick and re-runs are cheap.

**HERC relevance**: HERC's EXECUTE phase (remote backtest, typically 2–10 min per alpha config) would benefit from Workflow resume if a 30+ parallel sweep is ever needed. But HERC's typical parallelism is 3–5, so interruption recovery is a minor concern. **Prompted dispatch is sufficient.**

**Verdict for team-forge**: Workflows are a win only if you're spawning 20+ agents with 5+ min runtime each and expect frequent interruptions. For focused research (5 parallel agents, 2 min per phase), **prompted dispatch avoids the session-scoping trap and keeps results in Claude's context**.

---

### 2.3 Human-in-the-Loop: Pause/Gate Points

**Workflow limitation** (official, [code.claude.com/docs/en/workflows](https://code.claude.com/docs/en/workflows#behavior-and-limits)):

> No mid-run user input. Only agent permission prompts can pause a run. For sign-off between stages, run each stage as its own workflow.

This is a **hard constraint**. Workflows cannot pause at custom gates (e.g., "synthesize hypotheses, then ask user which to test"). Workaround:
- Run each stage as a separate workflow
- Stage 1: `/workflow analyst_fanout` (background)
- **[user reviews results]**
- Stage 2: `/workflow implementer_dispatch` (new workflow with Stage 1 output as input)

**Prompted Dispatch**: Natively supports arbitrary pause points. The orchestrator agent can run Phase A, then turn over to the user for a decision, then resume Phase B with Claude deciding the orchestration.

**HERC relevance**: HERC has the **DEBATE phase**, which is fundamentally interactive:
1. Pre-consult (3 parallel analysts) produces `candidate_hypotheses`
2. **[Debate choreographed via peer-visible mailbox, user/teammates observe]**
3. Implementers synthesize rebutted hypotheses

The current `combiner-peer-debate` skill uses SendMessage() for asynchronous, multi-turn, human-observable coordination. This **cannot be implemented as a Workflow** without breaking up into multiple invocations.

**Verdict for team-forge**: If your pipeline has human decision gates, **mandatory prompted dispatch**. Workflows don't support mid-run user input. HERC's peer-debate pattern is a concrete example where Workflow would *break* the intended interactivity.

---

### 2.4 Visibility / Observability

**Workflow visibility** ([code.claude.com/docs/en/workflows](https://code.claude.com/docs/en/workflows#watch-the-run)):

```
/workflows           # List running/completed workflows
[select a run]
Enter / →           # Drill into phases, then agents
j / k               # Scroll within agent detail
```

Shows:
- Each phase with agent count, token total, elapsed time
- Per-agent: prompt, recent tool calls, result
- Progress updates in real-time

**Subagent visibility** (prompted dispatch):
- Each subagent dispatch is a turn in the orchestrator's conversation
- Full prompts visible inline
- Results land in the orchestrator's context
- Human reads the full reasoning turn by turn

**Observability: Token/Cost Tracing**:
- Workflows: [OpenObserve + OpenTelemetry](https://medium.com/devops-ai/openobserve-claude-code-end-to-end-ai-observability-984afcaeba36) gives token-by-token spend (requires setup)
- Prompted dispatch: `/usage` command breaks down by skill, subagent, MCP server

**HERC relevance**: HERC researchers want to **see each analyzer's hypothesis**, watch the debate unfold, and track implementer progress. The current text-based turn-by-turn flow is more transparent than the Workflow `/workflows` view for **observing reasoning**, though `/workflows` is better for **monitoring resource usage**.

**Verdict for team-forge**: If your users care about **reasoning transparency** (watching Claude think), use **prompted dispatch**. If your users care about **resource/progress dashboards** (token burn, wall time, phase % complete), **Workflows have a slight edge** with native `/workflows` view + OpenTelemetry integration. Hybrid: prompt dispatch + custom dashboard (HERC's planned approach).

---

### 2.5 Token Cost & Economics

**Workflow cost** (official, [code.claude.com/docs/en/costs](https://code.claude.com/docs/en/costs)):

> A workflow spawns many agents, so a single run can use meaningfully more tokens than working through the same task in conversation.

Specific guidance:
- Workflows apply "a repeatable quality pattern" (e.g., independent agents adversarially review each other's findings) — **this adds verification overhead**.
- Example: 100 agents each checking a module, then 1 synthesizer agent reading all 100 results → token cost = 100 × (module check tokens) + (synthesis tokens), potentially 5–10× a single-pass analysis.

**Agent team cost** ([code.claude.com/docs/en/costs#agent-team-token-costs]):

> Agent teams use approximately 7x more tokens than standard sessions when teammates run in plan mode, because each teammate maintains its own context window and runs as a separate Claude instance.

Guidance:
- Use Sonnet for teammates (lower cost than Opus)
- Keep teams small
- Keep spawn prompts focused
- Clean up teams when done

**Prompted dispatch cost** (implicit from SDK guidance):
- Each subagent invocation uses tokens for the prompt + agent loop
- Parallelism is limited by rate limits (Tier 1: ~5 concurrent agents before queuing)
- No verification overhead unless Claude explicitly codes it

**Token breakdown for a 3-agent HERC phase**:
- Orchestrator reads state: ~500 tokens
- Dispatch to 3 analyzers (parallel): 3 × ~2000 tokens = 6000
- Orchestrator synthesizes: ~1000 tokens
- **Total: ~7500 tokens per phase** (no verification)

Same phase via Workflow:
- Script write: ~500 tokens (one-time)
- 3 analyzers run (parallel): 3 × ~2000 = 6000 tokens
- Synthesizer + vote on claims: ~2000 tokens
- **Total: ~8500 tokens per phase** (with verification)

**Verdict for team-forge**: For small fan-outs (3–5 agents), **prompted dispatch is cheaper** unless you specifically want verification loops. Workflows break even (or become advantageous) when you fan out to 20+ agents and want cross-checking.

---

### 2.6 Composability & Nesting

**Workflows can invoke subagents** ([code.claude.com/docs/en/workflows](https://code.claude.com/docs/en/workflows#how-a-workflow-runs)):

> The runtime tracks each agent's result as the run progresses, which is what makes a run resumable within the same session.

Workflows are written in JavaScript; subagents are invoked via the workflow script. Example structure:
```javascript
const result = await agent("analyzer", { input });
```

**Subagents cannot nest** ([from Claude Code best practices](https://vanja.io/claude-code-skills-guide/)):

> Subagents cannot nest—a skill running in a forked subagent cannot spawn another subagent.

**Can a Workflow be invoked from a Skill?**
- Official docs are silent on this.
- Workflows are designed to run as commands (`/workflow-name`) or via Claude Code's `ask for a workflow` prompt.
- A Skill could theoretically invoke a workflow via Bash (`claude /workflow-name`), but this is not a documented, supported pattern.
- **Not recommended**: Workflows are top-level orchestration constructs, not composable sub-components.

**Can an Agent (from Agent SDK) invoke a Workflow?**
- Agent SDK gives programmatic access to agent() (spawn subagents) but NOT workflow() (write/run workflows).
- Workflows are a CLI/Desktop feature; Agent SDK does not expose workflow construction.
- **Conclusion**: Workflows and Agent SDK are complementary, not composable in the nesting sense.

**team-forge design implication**: If team-forge is a **Skill**, it cannot invoke Workflows internally. If team-forge is a **CLI extension**, it could shell out to Workflows, but this is awkward. **Best practice**: team-forge generates either:
1. Prompted agent orchestrators (current HERC pattern), or
2. Workflow scripts as standalone artifacts (user runs them separately)

Not both simultaneously.

**Verdict for team-forge**: **Do not use Workflows as internal sub-orchestration inside a Skill.** If you want Workflow-level scale and determinism, generate a standalone Workflow script (JavaScript) for the user to run independently. Keep the Skill on the prompted dispatch path.

---

## 3. Anti-Patterns & Limitations

### 3.1 Official Workflow Anti-Patterns

From community best practices and official guidance:

1. **Spawning sub-agents for serial work**: If agent B needs agent A's output, you cannot parallelize. Use sequential execution in the script. **Cost waste**: Queuing and context overhead.

2. **Bloated sub-agent prompts** (100–300 word sweet spot): Prompts > 300 words aren't specializing; they're just duplicating context. Keep focused.

3. **Not aggregating results**: Spawn 6 agents, dump outputs end-to-end → wasted isolation. **Synthesize instead.**

4. **Ignoring rate limits** (Tier 1 ~5 concurrent agents before queuing): If you spawn 16 concurrent agents on a low-tier plan, you get serial execution and pay parallel-agent costs with serial throughput.

### 3.2 Official Workflow Limits

- **Concurrency**: Up to 16 concurrent agents (bounded by CPU cores on local machine)
- **Total agents per run**: 1,000 agents
- **No filesystem/shell from script**: Agents read/write/run commands; script coordinates
- **Session-scoped resume**: Exit Claude Code → restart workflow fresh
- **No mid-run user input**: Only permission prompts can pause

### 3.3 Prompted Dispatch Anti-Patterns

Not officially documented, but evident from HERC experience:

1. **Re-dispatching agents after interruption**: No caching logic, so paused runs re-spawn all agents.
2. **Unbounded delegation**: No native limit on how many subagents can be spawned in one turn (rate limits apply).
3. **Losing context to token limits**: If results are large, Claude's context fills and earlier synthesis is lost. (Compaction helps, but it's reactive.)

---

## 4. Anthropic's Specific Patterns & Recommendations

### 4.1 "When to Use" Official Table

Directly from [**Orchestrate subagents at scale with dynamic workflows**](https://code.claude.com/docs/en/workflows#when-to-use-a-workflow):

| Criterion | Subagents | Skills | Workflows |
|---|---|---|---|
| What it is | A worker Claude spawns | Instructions Claude follows | A script the runtime executes |
| Who decides what runs next | Claude, turn by turn | Claude, following the prompt | The script |
| Where intermediate results live | Claude's context window | Claude's context window | Script variables |
| What's repeatable | The worker definition | The instructions | The orchestration itself |
| Scale | A few delegated tasks per turn | Same as subagents | Dozens to hundreds of agents per run |
| Interruption | Restarts the turn | Restarts the turn | Resumable in the same session |

### 4.2 Workflow Activation Patterns

**Option 1: Ask for a Workflow**
```
Include the word "workflow" in your prompt.
"Create a workflow to audit every API endpoint under src/routes/ for missing auth checks"
```

**Option 2: Ultracode**
```
/effort ultracode
# Claude decides when a task warrants a workflow (combines xhigh reasoning + automatic workflow orchestration)
```

**Option 3: Invoke a Bundled or Saved Workflow**
```
/deep-research <question>    # Built-in workflow
/<your-saved-workflow-name>  # Custom workflow
```

### 4.3 Orchestration Shapes (Five Patterns)

From [**Beyond One-Shot Prompts: 5 Claude Code Workflow Patterns Explained**](https://www.mindstudio.ai/blog/claude-code-agentic-workflow-patterns):

1. **Sequential**: Agent A → B → C (each depends on previous)
2. **Operator**: One agent decides and delegates to others
3. **Split-and-merge**: Parallelize independent tasks, then combine
4. **Agent Teams**: Persistent multi-agent collaboration with defined roles
5. **Headless**: No human interaction; purely automated

**HERC map**:
- **Phase B (SELECT → PRE-CONSULT → DISPATCH)**: Operator (researcher decides) + split-and-merge (3 parallel analyzers)
- **DEBATE**: Agent Teams pattern (peer-visible mailbox, multi-turn synthesis)
- **EXECUTE**: Sequential (remote backtest, then wait for result)

---

## 5. HERC-Specific Guidance

### 5.1 Current HERC Design (Prompted Dispatch)

**Strengths**:
- Orchestrator sees all results in context (full reasoning transparency)
- Debate phase is interactive and human-observable
- Researcher can inspect subagent outputs and decide next hypothesis dynamically
- Token cost is controlled (3–5 parallel agents per phase, typical 2–5 min runtime)
- Resumption via `--resume session_id` restores full context

**Weaknesses**:
- No built-in progress dashboard (mitigated by planned dashboard playground)
- Interruption requires manual re-prompting (no automatic cache)
- Token cost grows linearly with subagent count; no native parallelism beyond 5–7 agents
- No deterministic replay (if researcher exits, next session restarts orchestrator fresh)

### 5.2 Hybrid Option: Selective Workflow Integration

**Where Workflows Could Help (But Don't Shift HERC Entirely)**:

1. **SMOKE Phase** (Step 5):
   - **What it does**: Run champion baseline on remote server, validate reproducibility
   - **Why Workflow**: Deterministic, no human gates, single long-running agent
   - **Implementation**: Generate a `/smoke-baseline` workflow (JS script) that:
     - Spawns 1 agent to run `FORCE=true cron_code_promotion.sh`
     - Waits for result (resumable if interrupted)
     - Returns pass/fail verdict
   - **Benefit**: Replay same SMOKE with full cache if a network hiccup occurs

2. **EXECUTE Phase** (Step 6, multi-alpha backtest sweep):
   - **Current**: Dispatch 1 implementer per alpha sequentially OR parallelize in bash (error-prone)
   - **Workflow option**: Generate a `/execute-sweep` workflow that:
     - Fans out 10–20 parallel agents (1 per alpha config)
     - Each runs backtest on remote server
     - Synthesis: reads all results, computes IC/Sharpe/rank
   - **Benefit**: Native parallelism (up to 16 concurrent), resumable, intrinsic caching
   - **Trade-off**: EXECUTE moves out of the researcher's context; less interactive observation of per-alpha progress

3. **Pre-Consult Analyst Fan-out** (Step 2):
   - **Current**: Dispatch 3 analyzers in parallel via prompted agent
   - **Workflow option**: Generate a `/analyze-candidates` workflow to run 3–10 in parallel, synthesize
   - **Benefit**: Resumable if interrupted mid-analysis (rare, but useful for long-running NLM pre-consult)
   - **Trade-off**: Results live in script variables, not orchestrator context; less transparent

### 5.3 Recommended Approach for team-forge

**Do NOT attempt full Workflow migration for HERC.** Instead:

1. **Keep the core orchestrator as prompted Agent** (current herc-researcher pattern):
   - Phase B loop (SELECT → PRE-CONSULT → DISPATCH → MERGE → PERSIST → DECIDE) remains decision-driven
   - Debate phase remains interactive and human-observable
   - All intermediate results live in Claude's context for transparency

2. **Selectively generate Workflows for high-parallelism, deterministic phases**:
   - EXECUTE phase: Generate optional `/herc-execute-sweep` workflow if user opts in
   - Usage: Researcher can call it as `await workflow("herc-execute-sweep", { alphas, config })`
   - Or: Generate as a standalone script; user runs `/herc-execute-sweep` between DISPATCH and ANALYZE

3. **Document the hybrid approach**:
   - "HERC research is interactive (prompted dispatch). For large-scale backtests, you can use `/herc-execute-sweep` for deterministic, resumable parallelism."
   - Avoid conflating the two: don't try to run the entire 8-step loop as a Workflow.

4. **Provide team-forge with a config option**:
   ```yaml
   combiner: herc
   phases:
     pre_consult: dispatch  # Prompted agent
     execute: workflow      # Or: dispatch
     smoke: workflow        # Or: dispatch
   ```
   User selects the shape; team-forge generates accordingly.

---

## 6. Sources & References

### Official Anthropic Documentation

1. [**Orchestrate subagents at scale with dynamic workflows**](https://code.claude.com/docs/en/workflows) — Official Claude Code docs (May 2026)
   - Core decision table, use cases, limitations, resumption semantics
   
2. [**Introducing dynamic workflows in Claude Code**](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code) — Anthropic blog (May 2026)
   - Announcement of workflow feature, high-level use cases
   
3. [**Manage costs effectively**](https://code.claude.com/docs/en/costs) — Claude Code cost docs
   - Workflow token cost guidance, agent team cost (7x multiplier), rate limit recommendations
   
4. [**Agent SDK overview**](https://code.claude.com/docs/en/agent-sdk/overview) — Official SDK docs
   - Comparison of Agent SDK vs Claude Code CLI, session management, subagent nesting rules

5. [**Advanced tool use on the Claude Developer**](https://www.anthropic.com/engineering/advanced-tool-use) — Anthropic engineering blog
   - Programmatic tool calling, orchestration patterns

6. [**How we built our multi-agent research system**](https://www.anthropic.com/engineering/multi-agent-research-system) — Anthropic engineering blog
   - Distributed multi-agent coordination, synthesis patterns

### Community Guides & Analysis

7. [**Beyond One-Shot Prompts: 5 Claude Code Workflow Patterns Explained**](https://www.mindstudio.ai/blog/claude-code-agentic-workflow-patterns) — MindStudio (May 2026)
   - Detailed breakdown of 5 orchestration shapes with examples

8. [**Claude Code Workflows: Deterministic Multi-Agent Orchestration**](https://alexop.dev/posts/claude-code-workflows-deterministic-orchestration/) — alexop.dev
   - Determinism boundaries, when script control is necessary

9. [**Claude Code Best Practice: Orchestration Workflow**](https://github.com/shanraisshan/claude-code-best-practice/blob/main/orchestration-workflow/orchestration-workflow.md) — Community best practice GitHub
   - Anti-patterns, parallelism rules, rate limit considerations

10. [**CLAUDE CODE ORCHESTRATION**](https://kenhuangus.substack.com/p/claude-code-orchestration-dynamic) — Ken Huang, Agentic AI (Substack)
    - Deep analysis of orchestration primitives, when to choose each

11. [**OpenObserve + Claude Code: End-to-End AI Observability**](https://medium.com/devops-ai/openobserve-claude-code-end-to-end-ai-observability-984afcaeba36) — Medium (Apr 2026)
    - Observability integration with Workflows via OpenTelemetry

12. [**Claude Code Skills: The Complete Guide (2026)**](https://vanja.io/claude-code-skills-guide/) — vanja.io
    - Skill composability, nesting limits, when to use skills vs workflows vs subagents

---

## 7. Conclusions & Recommendations for team-forge

### 7.1 Decision Algorithm

**For a forged team pipeline, ask in order**:

1. **Is the orchestration shape unknown until runtime?** (e.g., researcher decides next hypothesis dynamically)
   → **Use prompted Agent dispatch**

2. **Is there a human decision gate between phases?** (e.g., user reviews and approves next step)
   → **Use prompted Agent dispatch** (Workflows don't support mid-run user input)

3. **Do you fan out to 20+ agents and want cross-verification?**
   → **Use Workflow** (token cost of verification is justified)

4. **Is the shape deterministic and repeatable, and is interruption-recovery important?**
   → **Use Workflow** (resumable caching is a win)

5. **Do you need full result transparency in the orchestrator's context?**
   → **Use prompted Agent dispatch** (Workflow results live in script variables)

**For HERC specifically**: Questions 1, 2, and 5 point to **prompted dispatch**. The entire orchestrator remains dispatch-based. Optionally use Workflows for isolated phases (EXECUTE, SMOKE) only if parallelism or resumability is a priority.

### 7.2 No One-Size-Fits-All Answer

- **Workflows are not a drop-in replacement for prompted dispatch.** They solve a different problem.
- **Prompted dispatch is not strictly cheaper.** It's cheaper for small fan-outs; Workflows break even at 20+ agents if verification adds value.
- **Hybrid is valid**: Use prompted orchestrators for interactive research, generate Workflows for deterministic high-parallelism phases.

### 7.3 Recommendation for team-forge MVP

1. **Default to prompted Agent dispatch** for all generated orchestrators.
2. **Support a `phase_orchestration` config** in forged team specs:
   ```yaml
   phases:
     pre_consult:
       orchestration: dispatch  # or: workflow
       parallel_agents: 3
   ```
3. **Document the trade-offs** in the forged team's spec:
   - "This phase is interactive (prompted dispatch) to enable researcher decision-making."
   - "This phase is deterministic (workflow) for reproducible, large-scale parallelism."
4. **Plan a future enhancement**: Generate optional Workflow scripts for high-parallelism phases (EXECUTE, audit sweeps) once team-forge has proven prompted dispatch patterns.

---

**Report prepared by**: Claude Code Guide Agent  
**Sources**: 12 official + community references (see Section 6)  
**Not documented**: Exact token-by-token cost breakdown for Workflow vs dispatch (varies by task); nesting Workflows inside Skills (not a supported pattern, inferred from docs).
