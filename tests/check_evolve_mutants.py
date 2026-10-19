#!/usr/bin/env python3
"""Mutation check for the evolve pass lint and teardown's judge gate.

Each mutant removes or weakens one rule in tools/ (a copy of the repo under /tmp, never the
working tree) and runs tests/check_evolve.py and tests/check_teardown_gate.py against it. A
mutant that leaves both green names a rule no test can fail. An unmutated copy runs first and
must pass, so a kill means the mutant, not a broken copy.

Usage:  python3 tests/check_evolve_mutants.py      (about seven minutes)
Exit 0 = every mutant killed; exit 1 = a mutant survived, or a pattern no longer matches.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORK = Path("/tmp/test-team-forge-evolve-mutants")
TESTS = ("tests/check_evolve.py", "tests/check_teardown_gate.py")

MINE, GATE, VOCAB = "tools/evolve_mine.py", "tools/teardown_ledger_gate.py", "tools/ledger_vocab.py"
MUTANTS = [
    # lesson events, every schema
    ("status compared case-sensitively", MINE, 'status = str(pl.get("status") or "").lower()', 'status = str(pl.get("status") or "")'),
    ("evidence type compared case-sensitively", MINE, 'etype = str(ev.get("type") or "").lower()', 'etype = str(ev.get("type") or "")'),
    (
        "budget_attribution dropped from the allowed types",
        VOCAB,
        'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote"}',
        'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote", "budget_attribution"}',
    ),
    (
        "allow-list turned into an anecdote deny-list",
        MINE,
        'if status == "applied" and (etype not in ADMISSIBLE_EVIDENCE if schema >= 2',
        'if status == "applied" and (etype == "anecdote" if schema >= 2',
    ),
    ("schema 1 lets an anecdote apply", MINE, '                                    else etype == "anecdote"):', "                                    else False):"),
    ("unknown status accepted", MINE, "if status not in LESSON_STATUSES:", "if False:"),
    ("withdrawn id flagged", MINE, 'if status != "rejected":', "if True:"),
    (
        "unresolved id accepted",
        MINE,
        'if status != "rejected":\n                defects.append(f"{label}: names {raw}',
        'if False:\n                defects.append(f"{label}: names {raw}',
    ),
    ("applied vs Candidates unchecked", MINE, 'elif status == "applied" and section == "candidates":', "elif False:"),
    ("applied prune left in Active accepted", MINE, 'elif status == "applied" and prune and section == "active":', "elif False:"),
    ("non-applied vs table unchecked", MINE, 'elif status in ("candidate", "queued", "rejected") and section != "candidates" \\', 'elif False and section != "candidates" \\'),
    (
        "non-applied may name Superseded",
        MINE,
        'elif status in ("candidate", "queued", "rejected") and section != "candidates" \\',
        'elif status in ("candidate", "queued", "rejected") and section == "active" \\',
    ),
    ("prune exemption removed", MINE, '                and not (prune and section == "active"):', "                and True:"),
    ("first event per id wins", MINE, "by_id[norm_id(raw) or str(raw).strip()] = (t, e, pl, raw)", "by_id.setdefault(norm_id(raw) or str(raw).strip(), (t, e, pl, raw))"),
    ("claim corrections ignored", MINE, "if not c or not any(tj > t and cj == c for tj, cj in claims)]", "if True]"),
    ("an earlier event corrects", MINE, "if not c or not any(tj > t and cj == c for tj, cj in claims)]", "if not c or not any(tj != t and cj == c for tj, cj in claims)]"),
    # pass scope
    ("window ignored", MINE, "elif start <= t <= end:", "elif True:"),
    ("window open at the start", MINE, "elif start <= t <= end:", "elif t <= end:"),
    ("window closed at mined_at", MINE, "elif start <= t <= end:", "elif start < t <= end:"),
    ("window closed at last_run", MINE, "elif start <= t <= end:", "elif start <= t < end:"),
    ("unparseable ts ignored", MINE, '        if t is None:\n            defects.append(f"lesson event ts', '        if False:\n            defects.append(f"lesson event ts'),
    # the schema gate
    ("every stamp read as schema 1", MINE, "    return x if type(x) is int else 1", "    return 1"),
    ("every stamp read as schema 2", MINE, "    return x if type(x) is int else 1", "    return 2"),
    ("schema-2 inputs not required", MINE, "    if not grading_path or not snapshot:", "    if False:"),
    # schema 2: events
    ("refs not required", MINE, 'if schema >= 2 and status == "applied" and not refs:', "if False:"),
    (
        "applied with no id accepted",
        MINE,
        '            if schema >= 2 and status == "applied":\n                defects.append(f"{label}: status applied but names',
        '            if False:\n                defects.append(f"{label}: status applied but names',
    ),
    ("rejected-then-applied flip accepted", MINE, 'if set(map(str, refs)) <= set(map(str, old.get("refs") or [])):', "if False:"),
    ("pass labels unchecked", MINE, 'if parse_ts(pl.get("pass")) != parse_ts(evolve.get("mined_at")) or pl.get("mode") != evolve.get("mode"):', "if False:"),
    # schema 2: rows this pass added or amended
    ("added row needs no applied event", MINE, "if rid not in applied:", "if False:"),
    ("added row needs no grading entry", MINE, "if rid not in graded:", "if False:"),
    ("amended rows need no proof", MINE, "or row_id(r) in applied)]", ")]"),
    ("snapshot ignored", MINE, 'before_ids = {row_id(r) for r in parse_register(snap_path)[0]["active"]}', 'before_ids = {row_id(r) for r in tables["active"]}'),
    (
        "row evidence unchecked",
        MINE,
        '    for row in prove:\n        if not evidence_signal(cell(row, "evidence")):',
        '    for row in []:\n        if not evidence_signal(cell(row, "evidence")):',
    ),
    (
        "register alone held to the allow-list",
        MINE,
        '    for row in prove:\n        if not evidence_signal(cell(row, "evidence")):',
        '    for row in tables["active"]:\n        if not evidence_signal(cell(row, "evidence")):',
    ),
    ("one-word signals only", MINE, "    for n in (1, 2):", "    for n in (1,):"),
    ("named harm not accepted", MINE, "    if low.startswith(_NAMED_HARM):", "    if False:"),
    # grading entries
    ("green before run accepted", MINE, "if _run_exit(before) in (None, 0):", "if _run_exit(before) is None:"),
    ("bool exit counted as an integer", MINE, "return x if type(x) is int else None", "return x if isinstance(x, int) else None"),
    ("after run unchecked", MINE, "if _run_exit(after) != 0:", "if False:"),
    ("commands not compared", MINE, 'before["command"].strip() != after["command"].strip()', "False"),
    ("string passed accepted", MINE, 'if not isinstance(g.get("passed"), bool):', "if False:"),
    ("command type unchecked", MINE, 'not isinstance(run.get("command"), str)', "False"),
    # the judge file and its coverage
    ("judge verdict unchecked", MINE, 'if doc.get("verdict") != "PASS":', "if False:"),
    ("judge FAIL rows counted as PASS", MINE, 'elif verdict == "PASS":', "elif verdict:"),
    ("judge mined_at unchecked", MINE, 'if parse_ts(doc.get("mined_at")) is None or parse_ts(doc.get("mined_at")) != parse_ts(mined_at):', "if False:"),
    (
        "judge mined_at compared as text",
        MINE,
        'if parse_ts(doc.get("mined_at")) is None or parse_ts(doc.get("mined_at")) != parse_ts(mined_at):',
        'if doc.get("mined_at") != mined_at:',
    ),
    ("team seat accepted as judge", MINE, "if team and team.lower() in who:", "if False:"),
    ("team seat matched by prefix only", MINE, "if team and team.lower() in who:", 'if team and who.startswith(f"{team.lower()}-"):'),
    ("register team not read", MINE, "return m.group(1) if m else None", "return None"),
    ("judge brief unchecked", MINE, "if not (bp if bp.is_absolute() else path.parent / bp).is_file():", "if False:"),
    ("judge coverage unchecked", MINE, "        for rid in sorted(need - judged):", "        for rid in []:"),
    ("cycle rows not required", MINE, "need = {row_id(r) for r in prove} | cycle_rows(", "need = {row_id(r) for r in prove} or cycle_rows("),
    ("a judged close does not clear cycle rows", MINE, "and (since is None or made is None or made > since):", ":"),
    ("cycle rows ignore the mode", MINE, 'if pl.get("mode") == "cycle" and', "if"),
    ("earlier judge files ignored", MINE, 'if t and now and t < now and doc.get("verdict") == "PASS" and (best is None or t > best):', "if False:"),
    # --since
    ("--since compared as text", MINE, 'return [e for e in events if (parse_ts(e.get("ts")) or start) >= start]', 'return [e for e in events if str(e.get("ts") or "") >= since]'),
    # teardown's judge gate. Not listed: `git ls-files` in place of `git log`, which is
    # equivalent while the `git status` half stands -- any file in the index but not in a
    # commit shows there, and a gitignored file fails both.
    ("teardown skips the judge", GATE, "code, message = check_judge(repo_root, team, ledger, candidates_doc)", 'code, message = 0, "skipped"'),
    ("teardown accepts an uncommitted judge file", GATE, 'if not _git(repo_root, "log", "-n1", "--format=%H", "--", str(rel)).stdout.strip() \\', "if False and None \\"),
    ("teardown ignores edits after the commit", GATE, 'or _git(repo_root, "status", "--porcelain", "--", str(rel)).stdout.strip():', "or False:"),
    (
        "teardown ignores judge defects",
        GATE,
        '    if defects:\n        return 2, f"STALE -- {rel}: {defects[0]}"',
        '    if False:\n        return 2, f"STALE -- {rel}: {defects[0]}"',
    ),
    (
        "teardown ignores row coverage",
        GATE,
        '    if missing:\n        return 2, f"STALE -- {rel} has no PASS row',
        '    if False:\n        return 2, f"STALE -- {rel} has no PASS row',
    ),
    ("teardown ignores a dropped schema", GATE, "    if type(mined_under) is int and mined_under != schema:", "    if False:"),
    ("teardown demands a judge of schema-1 passes", GATE, "    if schema < 2:\n        return 0,", "    if False:\n        return 0,"),
    ("teardown takes any pass's judge file", GATE, 'if parse_ts(load_json(path, "judge file").get("mined_at")) == parse_ts(mined_at)]', "]"),
]


def fresh_copy():
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.copytree(REPO, WORK, ignore=shutil.ignore_patterns(".git", "__pycache__"))


def tests_pass():
    for t in TESTS:
        r = subprocess.run([sys.executable, str(WORK / t)], capture_output=True, text=True, timeout=600)
        if r.returncode:
            return False
    return True


def main():
    fresh_copy()
    if not tests_pass():
        print("✗ the unmutated copy fails its own tests — fix that before reading any kill")
        return 1
    survived, broken = [], []
    for name, rel, old, new in MUTANTS:
        fresh_copy()
        target = WORK / rel
        text = target.read_text()
        if text.count(old) != 1:
            broken.append(name)
            print(f"✗ pattern for {name!r} matches {text.count(old)} times in {rel}")
            continue
        target.write_text(text.replace(old, new))
        killed = not tests_pass()
        print(f"{'✓ killed  ' if killed else '✗ SURVIVED'} {name}")
        if not killed:
            survived.append(name)
    shutil.rmtree(WORK, ignore_errors=True)
    total = len(MUTANTS)
    print(
        f"\n{total - len(survived) - len(broken)} of {total} mutants killed" + (f"; survived: {survived}" if survived else "") + (f"; patterns stale: {broken}" if broken else "")
    )
    return 1 if survived or broken else 0


if __name__ == "__main__":
    sys.exit(main())
