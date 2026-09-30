#!/usr/bin/env python3
"""teardown_ledger_gate.py check — the harness for the script that replaces the jq
one-liner in skills/teardown/SKILL.md Step 1 with a real exit code.

What it proves:
  - each of the four freshness conditions (evolve marker exists, mode == close, no event
    postdates last_run, the candidates file's own mined_at agrees with no later sibling)
    is independently detected, with its own exit code and a message naming which failed
  - a mixed ISO-8601 ledger — some events "...Z", one "...+00:00" a fraction of a second
    later — is read by real chronological order, not by a plain string compare, where "."
    sorts before "Z" regardless of which timestamp is actually later
  - a timestamp that fails to parse is never treated as "before last_run" — that is the
    direction that would falsely call a run fresh and let its worktree be removed
  - the fresh case (all four conditions met) exits 0
  - `archive` copies the live ledger to docs/team-forge/<team>/final-ledger.json, and
    refuses with exit 1 when there is no live ledger to copy
  - a missing or unparseable ledger exits 3 (`check`) via UNREADABLE, distinct from every
    freshness verdict

And a meta-check: two mutant freshness functions (one reverting to a plain string compare,
one dropping the mode == close condition) are run against the same fixtures the positive
checks above use, and must disagree with the real script — proving those checks actually
discriminate correct behavior rather than passing on any output.

Usage:  python3 tests/check_teardown_gate.py
Exit 0 = all green; exit 1 = the gate's freshness logic drifted, or a check went blind.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "tools" / "teardown_ledger_gate.py"
sys.path.insert(0, str(REPO / "tools"))
from teardown_ledger_gate import check_freshness, parse_ts  # noqa: E402

WORK = Path("/tmp/test-team-forge-teardown-gate")


def _make_hub(name, ledger_doc, candidates_docs=None):
    """<WORK>/<name>/.claude/team-forge/<name>/tracker/status.json, plus any
    docs/team-forge/<name>/evolve/candidates-*.json fixtures. Returns the hub path."""
    target = WORK / name
    hub = target / ".claude" / "team-forge" / name
    (hub / "tracker").mkdir(parents=True, exist_ok=True)
    (hub / "tracker" / "status.json").write_text(json.dumps(ledger_doc))
    for fname, doc in (candidates_docs or {}).items():
        cdir = target / "docs" / "team-forge" / name / "evolve"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / fname).write_text(json.dumps(doc))
    return hub


def _run_check(hub):
    return subprocess.run([sys.executable, str(GATE), "check", str(hub)], capture_output=True, text=True)


def _run_archive(hub):
    return subprocess.run([sys.executable, str(GATE), "archive", str(hub)], capture_output=True, text=True)


def check_missing():
    hub = _make_hub("missing", {"events": []})
    r = _run_check(hub)
    assert r.returncode == 1, f"no evolve marker should exit 1\n{r.stdout}{r.stderr}"
    assert "MISSING" in r.stdout, r.stdout
    print("✓ MISSING: no evolve marker at all exits 1")


def check_stale_cycle_mode():
    hub = _make_hub(
        "cycle-mode",
        {
            "events": [{"ts": "2026-01-01T00:00:00Z"}],
            "evolve": {"mode": "cycle", "last_run": "2026-01-02T00:00:00Z"},
        },
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"cycle mode should exit 2\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout and "cycle" in r.stdout, r.stdout
    print("✓ STALE (mode): a cycle-mode pass does not satisfy teardown's close-mode bar")


def check_stale_event_after_last_run():
    hub = _make_hub(
        "late-event",
        {
            "events": [{"ts": "2026-01-03T00:00:00Z"}],
            "evolve": {"mode": "close", "last_run": "2026-01-02T00:00:00Z", "candidates": "x.json", "mined_at": "2026-01-02T00:00:00Z"},
        },
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"an event after last_run should exit 2\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout and "event" in r.stdout, r.stdout
    print("✓ STALE (event): an event later than last_run is never fresh")


def check_mixed_iso8601_formats_do_not_false_positive():
    # Real ledgers mix "...Z" with "...+00:00"/fractional-second timestamps. A plain
    # string compare sorts "." before "Z" regardless of real chronological order, so an
    # event genuinely half a second AFTER last_run, in a different format, would read as
    # earlier and falsely pass as fresh.
    hub = _make_hub(
        "mixed-formats",
        {
            "events": [{"ts": "2026-01-01T14:00:00.500000+00:00"}],
            "evolve": {"mode": "close", "last_run": "2026-01-01T14:00:00Z", "candidates": "x.json", "mined_at": "2026-01-01T14:00:00Z"},
        },
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"mixed-format later event should exit 2\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout, r.stdout
    print("✓ mixed ISO-8601 formats: parsed by real time, not by string order")


def check_unparseable_timestamp_is_conservative():
    hub = _make_hub(
        "bad-ts",
        {
            "events": [{"ts": "not-a-timestamp"}],
            "evolve": {"mode": "close", "last_run": "2026-01-02T00:00:00Z", "candidates": "x.json", "mined_at": "2026-01-02T00:00:00Z"},
        },
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"an unparseable timestamp must never look 'before' -- fail closed\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout, r.stdout
    print("✓ unparseable timestamp: never treated as earlier than last_run")


def check_stale_mined_at_mismatch():
    # evolve.candidates is REPO-RELATIVE (evolve's own Step 8 stamps it that way) -- using
    # the real shape here, not an absolute test path, is what exercises repo_root
    # resolution rather than accidentally passing regardless of it.
    team = "mined-at-mismatch"
    rel_candidates = f"docs/team-forge/{team}/evolve/candidates-2026-01-02.json"
    hub = _make_hub(
        team,
        {
            "events": [{"ts": "2026-01-01T00:00:00Z"}],
            "evolve": {
                "mode": "close",
                "last_run": "2026-01-02T00:00:00Z",
                "candidates": rel_candidates,
                "mined_at": "2026-01-02T00:00:00Z",
            },
        },
        candidates_docs={"candidates-2026-01-02.json": {"mined_at": "2026-01-01T23:00:00Z"}},
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"a mined_at mismatch should exit 2\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout and "mined_at" in r.stdout, r.stdout
    print("✓ STALE (mined_at mismatch): the marker must point at a real mining run")


def check_stale_later_candidates_file():
    team = "later-candidates"
    rel_candidates = f"docs/team-forge/{team}/evolve/candidates-2026-01-02.json"
    hub = _make_hub(
        team,
        {
            "events": [{"ts": "2026-01-01T00:00:00Z"}],
            "evolve": {"mode": "close", "last_run": "2026-01-02T00:00:00Z",
                       "candidates": rel_candidates, "mined_at": "2026-01-02T00:00:00Z"},
        },
        candidates_docs={
            "candidates-2026-01-02.json": {"mined_at": "2026-01-02T00:00:00Z"},
            "candidates-2026-01-03.json": {"mined_at": "2026-01-03T00:00:00Z"},
        },
    )
    r = _run_check(hub)
    assert r.returncode == 2, f"a later candidates file should exit 2\n{r.stdout}{r.stderr}"
    assert "STALE" in r.stdout and "candidates-2026-01-03.json" in r.stdout, r.stdout
    print("✓ STALE (later candidates file): a later mining pass means this marker is stale")


def check_fresh():
    team = "fresh"
    rel_candidates = f"docs/team-forge/{team}/evolve/candidates-2026-01-02.json"
    hub = _make_hub(
        team,
        {
            "events": [{"ts": "2026-01-01T00:00:00Z"}],
            "evolve": {"mode": "close", "last_run": "2026-01-02T00:00:00Z",
                       "candidates": rel_candidates, "mined_at": "2026-01-02T00:00:00Z"},
        },
        candidates_docs={"candidates-2026-01-02.json": {"mined_at": "2026-01-02T00:00:00Z"}},
    )
    r = _run_check(hub)
    assert r.returncode == 0, f"all four conditions met should exit 0\n{r.stdout}{r.stderr}"
    assert "fresh" in r.stdout, r.stdout
    print("✓ fresh: all four conditions met exits 0")


def check_unreadable():
    target = WORK / "unreadable"
    hub = target / ".claude" / "team-forge" / "unreadable"
    (hub / "tracker").mkdir(parents=True, exist_ok=True)
    (hub / "tracker" / "status.json").write_text("{not valid json")
    r = _run_check(hub)
    assert r.returncode == 3, f"malformed ledger should exit 3\n{r.stdout}{r.stderr}"
    assert "UNREADABLE" in r.stdout, r.stdout

    missing_hub = WORK / "no-such-hub" / ".claude" / "team-forge" / "no-such-hub"
    r = _run_check(missing_hub)
    assert r.returncode == 3, f"a hub with no ledger file should exit 3\n{r.stdout}{r.stderr}"
    assert "UNREADABLE" in r.stdout, r.stdout
    print("✓ UNREADABLE: malformed JSON and a missing ledger both exit 3, distinct from 1/2")


def check_archive():
    team = "archive-me"
    hub = _make_hub(team, {"events": [{"ts": "2026-01-01T00:00:00Z"}], "marker": "live"})
    r = _run_archive(hub)
    assert r.returncode == 0, f"archive should succeed\n{r.stdout}{r.stderr}"
    dest = WORK / team / "docs" / "team-forge" / team / "final-ledger.json"
    assert dest.is_file(), f"archive did not write {dest}"
    assert json.loads(dest.read_text()) == {"events": [{"ts": "2026-01-01T00:00:00Z"}], "marker": "live"}

    no_ledger_hub = WORK / "archive-nothing" / ".claude" / "team-forge" / "archive-nothing"
    r = _run_archive(no_ledger_hub)
    assert r.returncode == 1, f"archive with no live ledger should exit 1\n{r.stdout}{r.stderr}"
    assert "no ledger at" in r.stderr, r.stderr
    print("✓ archive: copies the live ledger to final-ledger.json; refuses with exit 1 when absent")


# --------------------------------------------------------------------------- the meta-check


def _mutant_string_compare(ledger, kb_dir):
    """Reverts the datetime fix -- compares timestamps as plain strings, the exact bug
    class this script was written to avoid."""
    evolve = ledger.get("evolve")
    if not evolve:
        return 1, "MISSING"
    if evolve.get("mode") != "close":
        return 2, "STALE mode"
    last_run = evolve.get("last_run") or ""
    events = [e for e in (ledger.get("events") or []) if isinstance(e, dict)]
    later = [e for e in events if (e.get("ts") or "") > last_run]
    if later:
        return 2, "STALE event"
    return 0, "fresh"


def _mutant_no_mode_check(ledger, kb_dir):
    """Drops the mode == close condition entirely -- a cycle-mode pass would pass."""
    evolve = ledger.get("evolve")
    if not evolve:
        return 1, "MISSING"
    last_run_dt = parse_ts(evolve.get("last_run") or "")
    events = [e for e in (ledger.get("events") or []) if isinstance(e, dict)]
    later = [e for e in events if parse_ts(e.get("ts")) and last_run_dt and parse_ts(e.get("ts")) > last_run_dt]
    if later:
        return 2, "STALE event"
    return 0, "fresh"


def check_meta():
    # The mixed-format ledger: the real fix reports STALE (code 2); the string-compare
    # mutant, fooled by "." sorting before "Z", reports fresh (code 0).
    mixed = {
        "events": [{"ts": "2026-01-01T14:00:00.500000+00:00"}],
        "evolve": {"mode": "close", "last_run": "2026-01-01T14:00:00Z", "candidates": "x.json", "mined_at": "2026-01-01T14:00:00Z"},
    }
    real_code, _ = check_freshness(mixed, None)
    mutant_code, _ = _mutant_string_compare(mixed, None)
    assert real_code == 2, f"the real check should be STALE on the mixed-format fixture, got {real_code}"
    assert mutant_code != real_code, (
        "the string-compare mutant agreed with the real check on the mixed-format fixture -- " "the mixed-format test above would pass on either implementation and prove nothing"
    )

    # The cycle-mode ledger: the real check reports STALE (2); the mode-blind mutant, which
    # never asks whether the pass was close-mode, reports fresh (0).
    cycle = {
        "events": [{"ts": "2026-01-01T00:00:00Z"}],
        "evolve": {"mode": "cycle", "last_run": "2026-01-02T00:00:00Z"},
    }
    real_code, _ = check_freshness(cycle, None)
    mutant_code, _ = _mutant_no_mode_check(cycle, None)
    assert real_code == 2, f"the real check should be STALE on a cycle-mode ledger, got {real_code}"
    assert mutant_code != real_code, (
        "the mode-blind mutant agreed with the real check on a cycle-mode ledger -- " "the cycle-mode test above would pass on either implementation and prove nothing"
    )
    print("✓ meta-check: 2 mutant freshness functions (string-compare, mode-blind) disagree " "with the real check on the exact fixtures the positive checks assert against")


def main():
    assert GATE.exists(), f"gate script not found at {GATE}"
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)

    check_missing()
    check_stale_cycle_mode()
    check_stale_event_after_last_run()
    check_mixed_iso8601_formats_do_not_false_positive()
    check_unparseable_timestamp_is_conservative()
    check_stale_mined_at_mismatch()
    check_stale_later_candidates_file()
    check_fresh()
    check_unreadable()
    check_archive()
    check_meta()

    print("\nALL TEARDOWN-GATE CHECKS PASSED")


if __name__ == "__main__":
    main()
