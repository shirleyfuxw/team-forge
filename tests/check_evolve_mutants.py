#!/usr/bin/env python3
"""Mutation check for the evolve pass lint and teardown's judge gate.

Each mutant removes or weakens one rule in tools/ (a copy of the repo under /tmp, never the
working tree) and runs tests/check_evolve.py and tests/check_teardown_gate.py against it. A
mutant that leaves both green names a rule no test can fail. An unmutated copy runs first and
must pass, so a kill means the mutant, not a broken copy.

Usage:  python3 tests/check_evolve_mutants.py      (about nine minutes)
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
    ('status compared case-sensitively', MINE, 'status = str(pl.get("status") or "").lower()', 'status = str(pl.get("status") or "")'),
    ('evidence type compared case-sensitively', MINE, 'etype = str(ev.get("type") or "").lower()', 'etype = str(ev.get("type") or "")'),
    ('budget_attribution dropped from the allowed types', VOCAB, 'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote"}', 'ADMISSIBLE_EVIDENCE = frozenset(EVIDENCE_TYPES) - {"anecdote", "budget_attribution"}'),
    ('allow-list turned into an anecdote deny-list', MINE, 'if status == "applied" and (etype not in ADMISSIBLE_EVIDENCE if schema >= 2', 'if status == "applied" and (etype == "anecdote" if schema >= 2'),
    ('schema 1 lets an anecdote apply', MINE, '                                    else etype == "anecdote"):', '                                    else False):'),
    ('unknown status accepted', MINE, 'if status not in LESSON_STATUSES:', 'if False:'),
    ('withdrawn id flagged', MINE, 'if status != "rejected":', 'if True:'),
    ('unresolved id accepted', MINE, 'if status != "rejected":\n                defects.append(f"{label}: names {raw}', 'if False:\n                defects.append(f"{label}: names {raw}'),
    ('applied vs Candidates unchecked', MINE, 'elif status == "applied" and section == "candidates":', 'elif False:'),
    ('applied prune left in Active accepted', MINE, 'elif status == "applied" and prune and section == "active":', 'elif False:'),
    ('non-applied vs table unchecked', MINE, 'elif status in ("candidate", "queued", "rejected") and section != "candidates" \\', 'elif False and section != "candidates" \\'),
    ('non-applied may name Superseded', MINE, 'elif status in ("candidate", "queued", "rejected") and section != "candidates" \\', 'elif status in ("candidate", "queued", "rejected") and section == "active" \\'),
    ('prune exemption removed', MINE, '                and not (prune and section == "active"):', '                and True:'),
    ('first event per id wins', MINE, 'by_id[norm_id(raw) or str(raw).strip()] = (t, e, pl, raw)', 'by_id.setdefault(norm_id(raw) or str(raw).strip(), (t, e, pl, raw))'),
    ('claim corrections ignored', MINE, 'if not c or not any(tj > t and cj == c for tj, cj in claims)]', 'if True]'),
    ('an earlier event corrects', MINE, 'if not c or not any(tj > t and cj == c for tj, cj in claims)]', 'if not c or not any(tj != t and cj == c for tj, cj in claims)]'),
    ('window ignored', MINE, 'elif start <= t <= end:', 'elif True:'),
    ('window open at the start', MINE, 'elif start <= t <= end:', 'elif t <= end:'),
    ('window closed at mined_at', MINE, 'elif start <= t <= end:', 'elif start < t <= end:'),
    ('window closed at last_run', MINE, 'elif start <= t <= end:', 'elif start <= t < end:'),
    ('unparseable ts ignored', MINE, '        if t is None:\n            defects.append(f"lesson event ts', '        if False:\n            defects.append(f"lesson event ts'),
    ('every stamp read as schema 1', MINE, '    schema, found = pass_schema(evolve, candidates)', '    schema, found = 1, []'),
    ('every stamp read as schema 2', MINE, '    schema, found = pass_schema(evolve, candidates)', '    schema, found = 2, []'),
    ('schema-2 inputs not required', MINE, '    if not grading_path or not snapshot:', '    if False:'),
    ('refs not required', MINE, 'if schema >= 2 and status == "applied" and not refs:', 'if False:'),
    ('applied with no id accepted', MINE, '            if schema >= 2 and status == "applied":\n                defects.append(f"{label}: status applied but names', '            if False:\n                defects.append(f"{label}: status applied but names'),
    ('rejected-then-applied flip accepted', MINE, 'if set(map(str, refs)) <= set(map(str, old.get("refs") or [])):', 'if False:'),
    ('pass labels unchecked', MINE, 'if parse_ts(pl.get("pass")) != parse_ts(evolve.get("mined_at")) or pl.get("mode") != evolve.get("mode"):', 'if False:'),
    ('added row needs no applied event', MINE, 'if rid not in applied:', 'if False:'),
    ('added row needs no grading entry', MINE, 'if rid not in graded:', 'if False:'),
    ('amended rows need no proof', MINE, 'prove = [r for r in tables["active"] if row_id(r) in changed or row_id(r) in applied]', 'prove = [r for r in tables["active"] if row_id(r) in changed]'),
    ('snapshot ignored', MINE, 'before = {row_id(r): text(r) for r in snap["active"]}', 'before = {row_id(r): text(r) for r in tables["active"]}'),
    ('row evidence unchecked', MINE, '    for row in prove:\n        if not evidence_signal(cell(row, "evidence")):', '    for row in []:\n        if not evidence_signal(cell(row, "evidence")):'),
    ('register alone held to the allow-list', MINE, '    for row in prove:\n        if not evidence_signal(cell(row, "evidence")):', '    for row in tables["active"]:\n        if not evidence_signal(cell(row, "evidence")):'),
    ('one-word signals only', MINE, '    for n in (1, 2):', '    for n in (1,):'),
    ('named harm not accepted', MINE, '    if low.startswith(_NAMED_HARM):', '    if False:'),
    ('green before run accepted', MINE, 'if _run_exit(before) in (None, 0):', 'if _run_exit(before) is None:'),
    ('bool exit counted as an integer', MINE, 'return x if type(x) is int else None', 'return x if isinstance(x, int) else None'),
    ('after run unchecked', MINE, 'if _run_exit(after) != 0:', 'if False:'),
    ('commands not compared', MINE, 'before["command"].strip() != after["command"].strip()', 'False'),
    ('string passed accepted', MINE, 'if not isinstance(g.get("passed"), bool):', 'if False:'),
    ('command type unchecked', MINE, 'not isinstance(run.get("command"), str)', 'False'),
    ('judge verdict unchecked', MINE, 'if doc.get("verdict") != "PASS":', 'if False:'),
    ('judge FAIL rows counted as PASS', MINE, 'elif verdict == "PASS":', 'elif verdict:'),
    ('judge mined_at unchecked', MINE, 'if parse_ts(doc.get("mined_at")) is None or parse_ts(doc.get("mined_at")) != parse_ts(mined_at):', 'if False:'),
    ('judge mined_at compared as text', MINE, 'if parse_ts(doc.get("mined_at")) is None or parse_ts(doc.get("mined_at")) != parse_ts(mined_at):', 'if doc.get("mined_at") != mined_at:'),
    ('team seat accepted as judge', MINE, 'if team and team.lower() in who:', 'if False:'),
    ('team seat matched by prefix only', MINE, 'if team and team.lower() in who:', 'if team and who.startswith(f"{team.lower()}-"):'),
    ('register team not read', MINE, 'return m.group(1) if m else None', 'return None'),
    ('judge brief unchecked', MINE, 'if not (bp if bp.is_absolute() else path.parent / bp).is_file():', 'if False:'),
    ('judge coverage unchecked', MINE, '        for rid in sorted(need - judged):', '        for rid in []:'),
    ('cycle rows not required', MINE, 'need = {row_id(r) for r in prove} | cycle_rows(', 'need = {row_id(r) for r in prove} or cycle_rows('),
    ('a judged close does not clear cycle rows', MINE, '                and (since is None or made > since):', '                and True:'),
    ('cycle rows ignore the mode', MINE, 'if pl.get("mode") != "close" and', 'if'),
    ('earlier judge files ignored', MINE, '        if t and now and t < now and (best is None or t > best) \\', '        if False and (best is None or t > best) \\'),
    ('--since compared as text', MINE, 'return [e for e in events if (parse_ts(e.get("ts")) or start) >= start]', 'return [e for e in events if str(e.get("ts") or "") >= since]'),
    ('teardown skips the judge', GATE, 'code, message = check_judge(repo_root, team, ledger, candidates_doc)', 'code, message = 0, "skipped"'),
    ('teardown ignores edits after the commit', GATE, 'or _git(repo_root, "status", "--porcelain", "--", str(rel)).stdout.strip():', 'or False:'),
    ('teardown ignores judge defects', GATE, '    if defects:\n        return 2, f"STALE -- {rel}: {defects[0]}"', '    if False:\n        return 2, f"STALE -- {rel}: {defects[0]}"'),
    ('teardown ignores row coverage', GATE, '    if missing:\n        return 2, f"STALE -- {rel} has no PASS row', '    if False:\n        return 2, f"STALE -- {rel} has no PASS row'),
    ('teardown ignores a dropped schema', GATE, '    if defects:\n        return 2, f"STALE -- {defects[0]}"', '    if False:\n        return 2, f"STALE -- {defects[0]}"'),
    ('teardown demands a judge of schema-1 passes', GATE, '    if schema < 2:\n        return 0,', '    if False:\n        return 0,'),
    ("teardown takes any pass's judge file", GATE, 'if parse_ts(load_json(path, "judge file").get("mined_at")) == parse_ts(mined_at)]', ']'),
    ('the lint ignores the candidates file', MINE, 'stamp, mined = evolve.get("schema"), candidates.get("pass_schema")', 'stamp, mined = evolve.get("schema"), evolve.get("schema")'),
    ('schema mismatch unchecked', MINE, '    if not defects and stamp != mined:', '    if False:'),
    ('stamp schema type unchecked', MINE, '    if "schema" in evolve and not _schema_ok(stamp):', '    if False:'),
    ('candidates schema type unchecked', MINE, '    if "pass_schema" in candidates and not _schema_ok(mined):', '    if False:'),
    ('candidates mined_at unchecked', MINE, '    if parse_ts(doc.get("mined_at")) != parse_ts(evolve.get("mined_at")):', '    if False:'),
    ('candidates file not read', MINE, '    candidates, cand_path, err = pass_candidates(evolve, ledger_path, candidates_path)', '    candidates, cand_path, err = {}, None, None'),
    ('a FAIL or invalid judge file clears cycle rows', MINE, '                and not judge_defects(jp, doc.get("mined_at"), team)[0]:', '                and True:'),
    ('an event with no pass label has no date', MINE, '        made = parse_ts(pl.get("pass")) or t', '        made = parse_ts(pl.get("pass"))'),
    ('an event with no mode is dropped', MINE, 'if pl.get("mode") != "close" and', 'if pl.get("mode") == "cycle" and'),
    ('text-only edits not detected', MINE, 'changed = {row_id(r) for r in tables["active"] if row_id(r) and before.get(row_id(r)) != text(r)}', 'changed = {row_id(r) for r in tables["active"] if row_id(r) and row_id(r) not in before}'),
    ('deleted Active rows accepted', MINE, '    for rid in sorted(set(before) - set(where), key=str):', '    for rid in []:'),
    ('the schema-2 era ignored', MINE, 'and made is not None and made >= era \\', 'and made is not None \\'),
    ('teardown trusts the disk copy of the judge file', GATE, '    if head.stdout != path.read_bytes() \\', '    if False \\'),
    ('teardown accepts a made-up commit', GATE, '    if not sha:\n        return 2,', '    if False:\n        return 2,'),
    ('teardown skips the ancestry check', GATE, '    if _git(repo_root, "merge-base", "--is-ancestor", sha, "HEAD").returncode:', '    if False:'),
    ('teardown ignores changes after the judged commit', GATE, '    if changed:\n        return 2, (f"STALE -- {\', \'.join(changed)} changed after', '    if False:\n        return 2, (f"STALE -- {\', \'.join(changed)} changed after'),
    ('teardown does not compare the grading file', GATE, '    seen = [str(register.relative_to(repo_root)), str((path.parent / "grading.json").relative_to(repo_root))]', '    seen = [str(register.relative_to(repo_root))]'),
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
