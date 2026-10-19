#!/usr/bin/env python3
"""Mutation check for the evolve pass lint and teardown's judge gate.

Each mutant removes or weakens one rule in tools/ (a copy of the repo under /tmp, never the
working tree) and runs tests/check_evolve.py and tests/check_teardown_gate.py against it. A
mutant that leaves both green names a rule no test can fail. An unmutated copy runs first and
must pass, so a kill means the mutant, not a broken copy.

Usage:  python3 tests/check_evolve_mutants.py      (about five minutes)
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
    # lesson events
    ("status compared case-sensitively", MINE, 'status = str(pl.get("status") or "").lower()', 'status = str(pl.get("status") or "")'),
    ("evidence type compared case-sensitively", MINE, 'etype = str(ev.get("type") or "").lower()', 'etype = str(ev.get("type") or "")'),
    (
        "budget_attribution dropped from the allowed types",
        VOCAB,
        'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote"}',
        'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote", "budget_attribution"}',
    ),
    ("allow-list turned into an anecdote deny-list", MINE, 'if status == "applied" and etype not in ADMISSIBLE_EVIDENCE:', 'if status == "applied" and etype == "anecdote":'),
    ("refs not required", MINE, 'if status == "applied" and not (isinstance(ev.get("refs"), list) and ev["refs"]):', "if False:"),
    ("unknown status accepted", MINE, "if status not in LESSON_STATUSES:", "if False:"),
    (
        "applied with no id accepted",
        MINE,
        '            if status == "applied":\n                defects.append(f"{label}: status applied but names',
        '            if False:\n                defects.append(f"{label}: status applied but names',
    ),
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
    ("first event per id wins", MINE, "by_id[norm_id(raw) or str(raw).strip()] = (e, pl, raw)", "by_id.setdefault(norm_id(raw) or str(raw).strip(), (e, pl, raw))"),
    ("claim corrections ignored", MINE, "if not c or not any(j > i and cj == c for j, cj in claims)]", "if True]"),
    # pass scope
    ("window ignored", MINE, "elif start <= t <= end:", "elif True:"),
    ("window open at the start", MINE, "elif start <= t <= end:", "elif t <= end:"),
    ("unparseable ts ignored", MINE, '        if t is None:\n            defects.append(f"lesson event ts', '        if False:\n            defects.append(f"lesson event ts'),
    # coverage of rows this pass added
    ("added row needs no applied event", MINE, "if rid not in applied:", "if False:"),
    ("added row needs no grading entry", MINE, "if rid not in graded:", "if False:"),
    ("snapshot ignored", MINE, 'added = [r for r in tables["active"] if row_id(r) and row_id(r) not in before_ids]', "added = []"),
    ("row evidence unchecked", MINE, 'if cell(row, "evidence") and not evidence_signal(cell(row, "evidence")):', "if False:"),
    ("one-word signals only", MINE, "for n in (1, 2):", "for n in (1,):"),
    # grading entries
    ("green before run accepted", MINE, "if _run_exit(before) in (None, 0):", "if _run_exit(before) is None:"),
    ("bool exit counted as an integer", MINE, "return x if type(x) is int else None", "return x if isinstance(x, int) else None"),
    ("after run unchecked", MINE, "if _run_exit(after) != 0:", "if False:"),
    ("commands not compared", MINE, 'before["command"].strip() != after["command"].strip()', "False"),
    ("string passed accepted", MINE, 'if not isinstance(g.get("passed"), bool):', "if False:"),
    (
        "command type unchecked",
        MINE,
        'if not isinstance(run, dict) or not isinstance(run.get("command"), str) \\\n            or not run["command"].strip():',
        'if not isinstance(run, dict) or not str(run.get("command") or "").strip():',
    ),
    # the judge file
    ("judge verdict unchecked", MINE, 'if doc.get("verdict") != "PASS":', "if False:"),
    ("judge FAIL rows counted as PASS", MINE, 'elif verdict == "PASS":', "elif verdict:"),
    ("judge mined_at unchecked", MINE, 'if doc.get("mined_at") != mined_at:', "if False:"),
    ("team seat accepted as judge", MINE, 'if team and who.startswith(f"{team.lower()}-"):', "if False:"),
    ("register team not read", MINE, "return m.group(1) if m else None", "return None"),
    ("judge brief unchecked", MINE, "if not (bp if bp.is_absolute() else path.parent / bp).is_file():", "if False:"),
    ("judge coverage unchecked", MINE, "for rid in sorted(({row_id(r) for r in added} | unjudged) - judged):", "for rid in []:"),
    ("unjudged rows not required", MINE, "for rid in sorted(({row_id(r) for r in added} | unjudged) - judged):", "for rid in sorted(({row_id(r) for r in added}) - judged):"),
    ("cycle carry-over unchecked", MINE, "for rid in sorted(applied - unjudged):", "for rid in []:"),
    # --since
    ("--since compared as text", MINE, 'return [e for e in events if (parse_ts(e.get("ts")) or start) >= start]', 'return [e for e in events if str(e.get("ts") or "") >= since]'),
    # teardown's judge gate
    ("teardown skips the judge", GATE, "code, message = check_judge(repo_root, team, mined_at)", 'code, message = 0, "skipped"'),
    ("teardown accepts an uncommitted judge file", GATE, "if tracked.returncode:", "if False:"),
    (
        "teardown ignores judge defects",
        GATE,
        '    if defects:\n        return 2, f"STALE -- {path.relative_to(repo_root)}: {defects[0]}"',
        '    if False:\n        return 2, f"STALE -- {path.relative_to(repo_root)}: {defects[0]}"',
    ),
    ("teardown takes any pass's judge file", GATE, 'if doc.get("mined_at") == mined_at:\n            found.append(path)', "if True:\n            found.append(path)"),
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
