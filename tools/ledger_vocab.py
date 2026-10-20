#!/usr/bin/env python3
"""The ledger's shared event vocabulary — one definition, two consumers.

Its own module, deliberately: `forge.py` parses argv and runs an entire forge at
import time, so importing the constant from there exits the process. This file has
no side effects and is safe to import from anywhere.
"""
from datetime import datetime, timezone

# The kinds the plugin's own skills document and the evolve miner recognizes. A team adds
# its own in design.yaml's `ledger.events`; the miner unions the two and treats everything ELSE as a lead-invented
# kind, i.e. a slot the schema did not have.
#
# Why that matters: a real 257-event run logged 78 distinct kinds, ~50 of them appearing
# exactly once — ad-hoc names like `future_leak_ok_schema_gap` invented mid-run because the
# vocabulary had no word for what happened. Each was a design defect nobody harvested. The
# `lesson` kind exists so a lead records one deliberately instead of minting a noun.
KNOWN_EVENT_KINDS = frozenset({
    # lifecycle
    "task_completed", "milestone_started", "milestone_completed",
    "cycle_started", "cycle_completed", "cycle_box_hit",
    # plan / contract movement
    "goal_revised", "replanned",
    # verification + lead discipline
    "gate_downgraded", "drift_corrected", "agent_blocked", "policy_adopted",
    # the evolve phase's own structured record
    "lesson",
})

# A `lesson` event's `evidence.type`: the miner's six admissible signals, an admitted memory
# note, and `anecdote`. skills/run and skills/evolve print this list verbatim.
EVIDENCE_TYPES = ("recurrence", "blocked_resolved", "gate_failure", "budget_attribution",
                  "policy_adopted", "lesson_event", "memory_note", "anecdote")
ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote"}
LESSON_STATUSES = ("candidate", "applied", "rejected", "queued")

# The evolve pass rules a candidates file was mined under; the evolve stamp copies it. Schema 2
# brought grading runs, coverage and the judge; a stamp without it predates them.
EVOLVE_PASS_SCHEMA = 2


def parse_ts(raw):
    """An ISO-8601 timestamp as an aware datetime, or None. Ledgers mix "...Z" with
    "+00:00", "+08:00" and fractional seconds, so a string compare misorders them; a value
    that fails to parse is None, never a string that sorts before everything."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
