# Agent-Teams Primitive — RE-VERIFICATION (2026-07-02)

**Supersedes the 2026-05-31 verification below.** Re-checked against live official
docs after the Claude Code agent-teams update. Primary sources fetched 2026-07-02:

- https://code.claude.com/docs/en/agent-teams.md  — agent teams (doc states "as of v2.1.178")
- https://code.claude.com/docs/en/sub-agents.md   — subagent/teammate frontmatter

**Verified by:** Claude Code expert agent + direct doc fetch, cross-checked against the
running Agent / Task* / SendMessage tool surface.

## TL;DR — what changed since 2026-05-31

1. ⚠️ **Agent teams are now EXPERIMENTAL and OFF by default.** They require
   `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json/env. Without it:
   *"no team is set up at session start, no team directories are written, and Claude
   does not spawn or propose teammates."* → **the team archetype does not function on a
   default install.** (agent-teams.md, top warning)
2. **One implicit team per session; named teams removed.** `TeamCreate`/`TeamDelete`
   tools no longer exist. `team_name` on the Agent tool is accepted-but-ignored.
   *"You can't create additional named teams or share a team across sessions."*
3. **Team/task paths are SESSION-DERIVED, not caller-named.** `team-name` = `session-`
   + first 8 chars of the session ID. Team config `~/.claude/teams/{team-name}/config.json`
   is deleted on session exit; task list `~/.claude/tasks/{team-name}/` **persists** across
   `/resume` (retention governed by `cleanupPeriodDays`). Agents should reach the list via
   the native `Task*` tools, not by hard-coding a caller-chosen path.
4. **Per-teammate `tools` + `model` ARE now honored** from the subagent definition; the
   definition body is appended to the teammate's system prompt. But **`skills` and
   `mcpServers` frontmatter are NOT applied when a definition runs as a teammate** —
   teammates load all project/user skills like a normal session. (`SendMessage` + the task
   tools are always available even when `tools` restricts everything else.)
5. **New subagent frontmatter fields:** `memory` (user|project|local), `isolation: worktree`,
   `effort`, `background`, `disallowedTools`, `permissionMode`, `color`, `initialPrompt`.
   `model` now accepts `fable` and full IDs; **default is `inherit`, not sonnet**.
6. **"Styles" ≠ agent-teams.** In current Claude Code, "styles" means session-level
   **output styles** (`~/.claude/output-styles/`); there is no per-agent/per-team `style`
   field. Orthogonal to rosters. (Note: team-forge's own "Workflow styles" term now collides
   with this platform term — see WORKFLOW-SCOPING.md.)

## Per-claim status vs. the 2026-05-31 doc

| Original claim | Now | Note |
|---|---|---|
| No native per-teammate / shared team memory | **Mostly holds** | Still no *shared team* memory. Per-agent `memory:` frontmatter now exists (`user`→`~/.claude/agent-memory/`). Docs do **not** confirm `memory:` applies to *teammates* (skills/mcpServers explicitly don't) — treat as subagent-only until verified. |
| Teammates independent context; lead history not carried | **STILL TRUE** | |
| Sharing via task list + mailbox + file I/O | **STILL TRUE** | `SendMessage` + shared task list + hooks (`TaskCreated`/`TaskCompleted`/`TeammateIdle`) all current. The `team_name` field in those hook payloads is deprecated (carries the session-derived name). |
| `/resume` + `/rewind` don't restore in-process teammates | **STILL TRUE** | rehydrate flow remains **necessary**. Task list persists; teammate sessions don't. |
| Team config `~/.claude/teams/{name}/`, tasks `~/.claude/tasks/{name}/` | **CHANGED** | `{name}` is session-derived, not caller-chosen. |
| "No per-teammate skill restriction enforced" | **PARTLY WRONG** | `tools`/`disallowedTools`/`model` ARE enforced per-teammate. `skills:` frontmatter is genuinely ignored for teammates — so the *skills* half of the claim is now explicitly doc-confirmed. |
| Feature requests: opt-in per-teammate memory, worktree isolation | **PARTIALLY SHIPPED** | `memory:` + `isolation: worktree` now exist as subagent frontmatter. |

## Impact on team-forge (files to change)

| Break | Severity | Files |
|---|---|---|
| team archetype assumes teams are always available | **HIGH** | README + launcher + forge: add a preflight for `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`; document the precondition |
| team/task paths hard-coded to project slug, not session-derived; teardown deletes now-auto-cleaned dirs | **HIGH** (wrong guidance; native `Task*` tools mitigate) | skills/rehydrate/SKILL.md, skills/teardown/SKILL.md, templates/team-launcher.md.j2, tools/forge.py |
| model enum `opus\|sonnet\|haiku`, "default sonnet" | LOW | templates/design.yaml.j2, tools/forge.py (add `fable`; note real default is `inherit`) |
| "skills advisory" note incomplete | LOW | templates/agent.md.j2, templates/design.yaml.j2 (add: `tools`/`model` ARE enforced per-teammate; `skills`/`mcpServers` ignored for teammates) |
| "styles" naming collision (Workflow styles vs. output styles) | LOW | WORKFLOW-SCOPING.md (glossary note) |

_Frozen `SCOPING.md` (v8.2) also encodes the old path model (lines ~139, ~246) and native
hook events (~337). Flagged for review; **not edited** here._

---

# Agent-Teams Memory Model Verification

**Date:** 2026-05-31  
**Status:** ⚠️ SUPERSEDED 2026-07-02 — see the re-verification banner at the top of this file. Findings below are preserved as the historical baseline; corrections are summarized above.  
**Sources:** Claude Code docs (`code.claude.com/docs`) + Claude API docs (`platform.claude.com`)  

---

## Summary of Findings

Agent-teams memory in Claude Code is **fundamentally different** from API-level Managed Agents memory:

- Claude Code agent-teams have **NO native per-teammate or shared memory mechanisms** documented
- Each teammate gets its own **independent context window** but no persistent storage layer
- Information sharing happens via: **task list, mailbox (SendMessage), and lead's synthesis only**
- Durable state requires **manual file operations** (Read/Write to project or user directories)
- The auto-memory system at `~/.claude/projects/.../memory/` is **session-scoped, not team-scoped**

---

## Question-by-Question Verification

### 1. Do teammates get their own memory directory out of the box?

**Finding: NO — not documented.**

**Evidence:**
- Agent-teams doc (https://code.claude.com/docs/en/agent-teams.md) makes NO mention of per-teammate memory directories
- Teammates have "own context window" (mentioned twice, confirmed) but NO memory store primitives
- Contrast: API-level Managed Agents get `memory_stores` with `/mnt/memory/` sandbox mounts (https://platform.claude.com/docs/en/managed-agents/memory.md)
- Claude Code agent-teams are **not the same system** as Managed Agents APIs

**Practical implication for team-forge:** Teammates cannot rely on persistent memory out-of-the-box. Design must use filesystem or lead-coordinated state.

---

### 2. If teammates have memory, where does it live? (exact path)

**Finding: NOT APPLICABLE — no native teammate memory.**

**Details:**
- Agent-teams do not expose a `memory_stores` API (that's Managed Agents only)
- No mention of `~/.claude/teammates/<name>/memory/` or similar
- Lead can read/write to **shared project files** (filesystem), but this is not a "memory system"—it's manual file I/O

**If you need persistent teammate state, design options:**
1. Lead writes coordination files to `.claude/agents/<team-name>/` (managed by lead, not teammates)
2. Teammates read/write to `.claude/` or project directory explicitly (risky for concurrent access)
3. Teammates return findings to lead via `SendMessage`; lead persists to disk manually

---

### 3. Who can write to teammate memory? Who can read it?

**Finding: N/A (no memory system), BUT file access is unrestricted.**

**Details:**
- Teammates run as independent Claude Code sessions with **standard file permissions**
- Each teammate can Read/Write/Bash like any regular session
- **No access control enforced by the team system itself**
- If you expose files (e.g., in `.claude/`), all teammates can access them
- Lead can also read teammate output files if they exist in the project directory

**Risk:** Concurrent writes from multiple teammates to the same file = race conditions. No locking primitives provided.

---

### 4. Lifecycle of teammate memory: Does it persist across `/clear`, `/resume`, or team destroy?

**Finding: EPHEMERAL (with caveats).**

**Details from docs:**
- **Session resumption limitation:** `/resume` and `/rewind` do NOT restore in-process teammates  
  > "No session resumption with in-process teammates: /resume and /rewind do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist."  
  (https://code.claude.com/docs/en/agent-teams.md#limitations)

- When lead is `/resume`'d, teammates are **gone** (in-process mode) or **disconnected** (split-pane mode)
- **Team cleanup** removes shared team resources:  
  > "Clean up the team... This removes the shared team resources."  
  (https://code.claude.com/docs/en/agent-teams.md#clean-up-the-team)

- **Team config and task list** are stored locally:
  - Team config: `~/.claude/teams/{team-name}/config.json`
  - Task list: `~/.claude/tasks/{team-name}/`  
  (https://code.claude.com/docs/en/agent-teams.md#architecture)

**Conclusion:** Teammate session state (context, conversation history) is ephemeral. Task list and config persist locally but are not "memory" in the durable sense. Any persistent data must be explicitly written to project/user directories.

---

### 5. Is there a "shared team memory" concept?

**Finding: NO shared memory namespace, but task list + mailbox serve that role.**

**Documented sharing mechanisms:**

| Mechanism | Scope | Read | Write | Persistence |
|-----------|-------|------|-------|-------------|
| **Task list** | Team-wide | All teammates + lead | Lead (or teammates claim/complete) | Local (`~/.claude/tasks/{team-name}/`) |
| **Mailbox** | 1-to-1 or broadcast | Recipient + lead | Any teammate, lead | Ephemeral (in-session) |
| **Team config** | Team-wide | All teammates (read `~/.claude/teams/{team-name}/config.json`) | Lead (auto-updated) | Local, auto-managed |
| **Explicit files** | Project-scoped | Any teammate + lead | Any teammate + lead | Yes (if saved to `.claude/` or project) |

**Key quote:**
> "How teammates share information: Automatic message delivery... Idle notifications... Shared task list... Teammate messaging: send a message to one specific teammate by name."  
(https://code.claude.com/docs/en/agent-teams.md#context-and-communication)

**No documented pattern for:** "Team-wide memory store that all teammates write to and read from." This would have to be custom (e.g., a `.claude/team-state.md` file that all teammates update).

---

### 6. How does auto-memory relate to agent-teams?

**Finding: DISTINCT SYSTEMS. Auto-memory is session-scoped, not team-scoped.**

**Auto-memory details** (from your CLAUDE.md):
- Location: `~/.claude/projects/<project-path>/memory/`
- Scope: **Per session** (user preferences, current task state, behavioral feedback)
- Read by: Subagents, the current session (via auto-context)
- Write by: Session's auto-memory hook (user/Claude, per-session)

**Agent-teams auto-memory:** NOT DOCUMENTED.
- No mention in agent-teams doc of teammates loading `~/.claude/projects/.../memory/`
- Likely teammates DO inherit project-level CLAUDE.md and MCP servers, but not lead's auto-memory directory
- Design assumption: **Teammates are independent sessions; they don't inherit lead's auto-memory, only project context**

**Quote from docs:**
> "When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. **The lead's conversation history does not carry over.**"  
(https://code.claude.com/docs/en/agent-teams.md#context-and-communication)

**Implication for team-forge:** If you want to pass durable context to teammates, use a shared file (e.g., `.claude/team-state.md`) or bake it into the spawn prompt, not auto-memory.

---

### 7. Memory primitives available to teammates

**Finding: Standard Claude Code file tools only (no Memory tool).**

**Available tools:**
- `Read` — read files from project/user directories
- `Write` — create/update files
- `Bash` — execute scripts (can create/manage state)
- `Edit` — modify code
- **No dedicated `Memory` tool**
- **No MCP server for memory management**

**Constraint:** Teammates cannot use Managed Agents memory APIs (those are API-only, not Claude Code).

**Best practice:** Teammates must coordinate via explicit file I/O to shared locations in `.claude/` or project root.

---

### 8. Documented best practices for multi-agent memory

**Finding: Minimal guidance; emphasis on task list, not shared memory.**

**From agent-teams best practices:**

> "**Give teammates enough context:** Teammates load project context automatically, including CLAUDE.md, MCP servers, and skills, but they don't inherit the lead's conversation history."  
(https://code.claude.com/docs/en/agent-teams.md#best-practices)

> "**Avoid file conflicts:** Two teammates editing the same file leads to overwrites. Break the work so each teammate owns a different set of files."  
(https://code.claude.com/docs/en/agent-teams.md#best-practices)

**What's NOT documented:**
- How to design cross-team memory
- Patterns for concurrent writes to shared state
- Audit trails for durable findings
- Memory lifecycle within a team cohort (e.g., delete after research ends)

**Inference:** Claude Code expects teammates to work on **separate files**, not shared memory. Any cross-team coordination happens via task list + mailbox, not a persistent store.

---

## Implications for team-forge Design

### Architecture Recommendation

1. **No per-teammate memory directory.** Design team-forge to rely on:
   - Lead-managed `.claude/agents/<team-name>/state/` (lead writes, teammates read)
   - Explicit mailbox for ad-hoc messages
   - Task list for work coordination

2. **Shared state model:** If teammates must collaborate on durable state (e.g., research findings), use a **lead-coordinated file** in `.claude/team-state.md`:
   - Lead reads/aggregates after each teammate message
   - Teammates don't write to it directly (avoids race conditions)
   - Alternative: teammates append to a log file with message ID to prevent overwrites

3. **No memory inheritance from lead's auto-memory.** Teammates are independent sessions. Pass context explicitly via:
   - `.claude/CLAUDE.md` (project-level guidance)
   - Spawn prompt (task-specific context)
   - Shared reference files (read-only setup docs)

4. **Audit & recovery:** Since teammate state is ephemeral, capture findings to `.claude/` or task list before team cleanup.

### Known Gaps in Claude Code Agent-Teams

**Feature requests for Anthropic:**
- Opt-in per-teammate persistent memory (like Managed Agents `memory_stores`)
- Team-level memory store (shared by all teammates, isolated per team)
- Safe concurrent write primitives (file locking, optimistic concurrency)
- Teammate memory lifecycle hooks (auto-cleanup on team destroy)
- Integration of auto-memory with teams (inherit or opt-in to lead's memory)

---

## Document Source URLs

| Question | Primary Source |
|----------|---|
| Agent-teams overview, architecture, memory | https://code.claude.com/docs/en/agent-teams.md |
| Managed Agents memory (API-level) | https://platform.claude.com/docs/en/managed-agents/memory.md |
| Managed Agents multiagent (API-level) | https://platform.claude.com/docs/en/managed-agents/multi-agent.md |
| Auto-memory scope and lifecycle | https://code.claude.com/docs/en/auto-memory.md (404 — not found) |

**Note:** `auto-memory.md` returns 404, so auto-memory details inferred from agent-teams context ("lead's conversation history does not carry over") and CLAUDE.md conventions.

---

## Verification Status

- [x] Claim 1 (per-teammate memory): **REFUTED** — not documented
- [x] Claim 2 (memory path): **N/A** — no native memory system
- [x] Claim 3 (access control): **CLARIFIED** — no access control; standard file permissions
- [x] Claim 4 (lifecycle): **VERIFIED EPHEMERAL** — teammates gone on `/resume`; task list/config local
- [x] Claim 5 (shared memory): **REFUTED** — no memory namespace; task list + mailbox only
- [x] Claim 6 (auto-memory inheritance): **CLARIFIED DISTINCT** — auto-memory session-scoped, not team-scoped
- [x] Claim 7 (primitives): **VERIFIED** — standard file tools only; no Memory tool for teams
- [x] Claim 8 (best practices): **MINIMAL** — emphasize separate files, avoid conflicts; no shared memory guidance

---

## Conclusion

Claude Code agent-teams are a **coordination primitive**, not a **memory system**. All persistent state must be managed explicitly by the lead or via manual file I/O. This is fundamentally different from Managed Agents (API), which provide `memory_stores` as a first-class feature.

For team-forge, design teammates as stateless workers that communicate findings back to the lead, which centralizes state management.

