# drain-lead memory

Fixture for a memory file with NO `## <cycle-id>` headings — the shape native agent memory
takes when nobody told the agent to section it, which is most of them. Every bullet below
was skipped in silence while `source.memory_dirs` still listed the file as mined, so the
document read "nothing to learn" rather than "not parsed". Mining it must warn and surface
these as anecdotes under one section. Mine with:

    --memory-dir tests/fixtures/evolve/agent-memory-flat

- Dispatching a wave of four saturates this machine; three finish sooner than four do.
- The plan-gate route parks an item without telling the human, so nobody approves it until the next cycle.
- Worktree prune has to run before the next dispatch or the migration lock is still held.
