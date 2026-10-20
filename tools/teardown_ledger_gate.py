#!/usr/bin/env python3
"""Enforces team-forge:teardown Step 1 with a real exit code, instead of a jq command an
agent types by hand and can skip or misread.

skills/teardown/SKILL.md Step 1 asks two things before Step 2 removes any worktree: that
`team-forge:evolve` has run in close mode against the final state (five conditions: an
`evolve` marker exists, its `mode` is `close`, no ledger event postdates its `last_run`,
its `candidates` file's own `mined_at` matches with no later candidates file sitting
next to it, and -- for a schema-2 stamp -- a committed `agent_evals/<team>/*/judge.json` for
that `mined_at` says PASS for every row the pass must have judged),
and that the live ledger gets copied to `docs/team-forge/<team>/final-ledger.json` before it
is gone.

Usage:
  teardown_ledger_gate.py check <hub-or-repo-path> [--team NAME]
  teardown_ledger_gate.py archive <hub-or-repo-path> [--team NAME]

Exit codes (check):
  0  fresh -- evolve has run in close mode against this final state. Safe to continue.
  1  MISSING -- no evolve pass has ever stamped this hub. Run evolve (close mode) first.
  2  STALE -- last pass was cycle mode, the ledger carries events after last_run, the
     candidates marker doesn't check out, or no committed PASS judge.json covers the pass.
     Run evolve (close mode), or its Step 9 judge, first.
  3  bad usage, or the ledger/design could not be read.

Exit codes (archive):
  0  docs/team-forge/<team>/final-ledger.json written.
  1  bad usage, or no live ledger to archive.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evolve_mine import (cell, downgrade_defect, judge_defects, judge_rows,  # noqa: E402
                         ledger_lessons, load_json, norm_id, parse_register, pass_schema,
                         register_sections, resolve_hub, row_id)
from ledger_vocab import parse_ts  # noqa: E402,F401  (re-exported for the tests)


def check_freshness(ledger, repo_root, team=None):
    """The five conditions SKILL.md Step 1.1 names, in order. Returns (exit_code, message).
    Every branch that cannot fully verify freshness reports STALE rather than fresh --
    an un-verifiable ledger is a reason to run evolve again, never a green light.

    `repo_root` resolves `evolve.candidates`: evolve's own Step 8 stamps it repo-relative
    (e.g. "docs/team-forge/<team>/evolve/candidates-<mined_at>.json"), so resolving it against
    the process's cwd instead of the repo root finds nothing whenever this runs from
    anywhere else -- which is every real invocation, since Step 1's own command passes the
    hub path, not the repo root, as cwd. Callers with no repo_root to resolve against (the
    meta-check's mutants) never reach this branch."""
    evolve = ledger.get("evolve")
    if not evolve:
        return 1, "MISSING -- no evolve pass has ever stamped this hub"

    mode = evolve.get("mode")
    last_run = evolve.get("last_run") or ""
    if mode != "close":
        return 2, f"STALE -- last pass was {mode!r} mode at {last_run}"

    last_run_dt = parse_ts(last_run)
    events = [e for e in (ledger.get("events") or []) if isinstance(e, dict)]
    event_dts = [parse_ts(e.get("ts")) for e in events]
    if last_run_dt is None or any(dt is None for dt in event_dts):
        return 2, "STALE -- last_run or an event timestamp could not be parsed"
    later = sum(1 for dt in event_dts if dt > last_run_dt)
    if later:
        return 2, f"STALE -- the ledger carries {later} event(s) after {last_run}"

    candidates_path = evolve.get("candidates")
    mined_at = evolve.get("mined_at")
    if not candidates_path or not mined_at:
        return 2, "STALE -- evolve.candidates/mined_at missing, cannot confirm the marker points at a real mining run"
    candidates_file = Path(candidates_path)
    if not candidates_file.is_absolute() and repo_root is not None:
        candidates_file = repo_root / candidates_file
    candidates_doc = load_json(candidates_file, "candidates file")
    if candidates_doc.get("mined_at") != mined_at:
        return 2, (f"STALE -- {candidates_path}'s own mined_at "
                   f"({candidates_doc.get('mined_at')!r}) does not match the ledger's marker ({mined_at!r})")
    evolve_dir = candidates_file.parent
    if evolve_dir.is_dir():
        later_candidates = sorted(
            f.name for f in evolve_dir.glob("candidates-*.json")
            if load_json(f, "candidates file").get("mined_at", "") > mined_at
        )
        if later_candidates:
            return 2, f"STALE -- a later candidates file exists: {', '.join(later_candidates)}"

    code, message = check_judge(repo_root, team, ledger, candidates_doc)
    if code:
        return code, message
    return 0, f"fresh · {candidates_path} · mined_at {mined_at} · {message}"


def _git(repo_root, *args):
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)


_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def named_files(repo_root, hub, register, sha, judged, tables, ledger):
    """Repo-relative paths the judged rows name, in their Applied-to cells (markdown links read
    from the register's folder) or their lesson events' targets, as they stand now or stood at
    the judged commit. `L2:design.yaml#gates.x` names the hub's design.yaml; an absolute path
    counts when it lies inside the repo; a bare word in a cell counts only as a file, so prose
    that mentions a folder does not pull the folder in."""
    root = repo_root.resolve()
    texts = [(cell(r, "applied to"), register.parent) for r in tables["active"] if row_id(r) in judged]
    texts += [(str((e.get("payload") or {}).get("target") or ""), None) for _t, e in ledger_lessons(ledger)
              if norm_id((e.get("payload") or {}).get("register_id")) in judged]
    found = []

    def add(path, folders=True):
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            return False
        if str(rel) in (".", "") or str(rel) in found:
            return str(rel) in found
        here = root / rel
        kind = ("blob" if here.is_file() else "tree" if here.is_dir() else
                _git(repo_root, "cat-file", "-t", f"{sha}:{rel}").stdout.strip())
        if kind == "blob" or kind == "tree" and folders:
            found.append(str(rel))
            return True
        return False

    for text, link_base in texts:
        for target in _LINK.findall(text):
            target = target.split("#", 1)[0]
            if target and not re.match(r"^[a-z]+:", target):
                add((link_base or root) / target)
        for token in re.split(r"[\s;,+·]+", _LINK.sub(" ", text)):
            token = re.sub(r"^L\d:", "", token.strip("`*()[]")).split("#", 1)[0]
            if not token or "/" not in token and not re.search(r"\.[A-Za-z0-9]+$", token):
                continue
            if Path(token).is_absolute():
                add(Path(token))
                continue
            for base in (root, hub, register.parent):
                if add(base / token, folders=link_base is None):
                    break
    return found


def check_judge(repo_root, team, ledger, candidates_doc):
    """A schema-2 close pass is finished only once a judge that did not produce it passed every
    row it had to, in a judge.json committed with the pass (evolve SKILL.md Step 9). A stamp
    from before that rule (schema 1) needs none."""
    evolve = ledger["evolve"]
    schema, defects = pass_schema(evolve, candidates_doc)
    if defects:
        return 2, f"STALE -- {defects[0]}"
    evolve_dir = repo_root / "docs" / "team-forge" / team / "evolve" if repo_root and team else None
    if schema < 2:
        down = downgrade_defect(ledger, evolve_dir) if evolve_dir else None
        if down:
            return 2, f"STALE -- {down}"
        return 0, "schema 1: the pass predates the judge rule"
    if repo_root is None or not team:
        return 2, "STALE -- no repo root and team to find agent_evals/<team>/*/judge.json in"
    mined_at = evolve.get("mined_at")
    judges = repo_root / "agent_evals" / team
    found = [path for path in sorted(judges.glob("*/judge.json"))
             if parse_ts(load_json(path, "judge file").get("mined_at")) == parse_ts(mined_at)]
    if not found:
        return 2, (f"STALE -- no agent_evals/{team}/*/judge.json for mined_at {mined_at}; "
                   f"run the evolve Step 9 judge")
    path = found[-1]
    rel = path.relative_to(repo_root)
    defects, judged = judge_defects(path, mined_at, team)
    if defects:
        return 2, f"STALE -- {rel}: {defects[0]}"
    register = repo_root / "docs" / "team-forge" / team / "lessons.md"
    if not register.is_file():
        return 2, f"STALE -- no register at {register.relative_to(repo_root)} to read the judged rows from"
    tables = parse_register(register)[0]
    where = register_sections(tables)
    missing = judge_rows(ledger, where, judges, team, schema, evolve_dir) - judged
    if missing:
        return 2, f"STALE -- {rel} has no PASS row for {', '.join(sorted(missing))}"
    # HEAD holds the file byte for byte, so index flags such as --assume-unchanged cannot
    # hide a rewrite, and nothing about it is staged or pending.
    head = subprocess.run(["git", "-C", str(repo_root), "show", f"HEAD:{rel}"], capture_output=True)
    if head.stdout != path.read_bytes() \
            or _git(repo_root, "status", "--porcelain", "--", str(rel)).stdout.strip():
        return 2, f"STALE -- {rel} is not committed as it stands; commit it with the pass"
    named = str(load_json(path, "judge file").get("commit") or "")
    sha = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{named}^{{commit}}").stdout.strip()
    if not sha:
        return 2, f"STALE -- {rel} names commit {named!r}, which this repository does not have"
    if _git(repo_root, "merge-base", "--is-ancestor", sha, "HEAD").returncode:
        return 2, f"STALE -- {rel} judged {sha[:12]}, which is not an ancestor of HEAD"
    record = [str(register.relative_to(repo_root)), str((path.parent / "grading.json").relative_to(repo_root))]
    if _git(repo_root, "status", "--porcelain", "--", *record).stdout.strip():
        return 2, f"STALE -- {' or '.join(record)} has an uncommitted change the judge never saw"
    seen = record + named_files(repo_root, repo_root / ".claude" / "team-forge" / team, register, sha,
                                judged, tables, ledger)
    changed = _git(repo_root, "diff", "--name-only", sha, "HEAD", "--", *seen).stdout.split()
    if changed:
        return 2, (f"STALE -- {', '.join(changed)} changed after the judged commit {sha[:12]}, so "
                   f"the judge never saw it; judge the pass again")
    return 0, f"judged PASS in {rel} (commit {sha[:12]})"


def cmd_check(args):
    hub, repo_root, team = resolve_hub(args.path, args.team)
    ledger_path = hub / "tracker" / "status.json"
    if not ledger_path.is_file():
        print(f"UNREADABLE -- no ledger at {ledger_path}")
        return 3
    ledger = load_json(ledger_path, "ledger")
    if not ledger:
        print(f"UNREADABLE -- {ledger_path} did not parse")
        return 3
    code, message = check_freshness(ledger, repo_root, team)
    print(message)
    return code


def cmd_archive(args):
    hub, repo_root, team = resolve_hub(args.path, args.team)
    ledger_path = hub / "tracker" / "status.json"
    if not ledger_path.is_file():
        print(f"ERROR: no ledger at {ledger_path}", file=sys.stderr)
        return 1
    dest_dir = repo_root / "docs" / "team-forge" / team
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "final-ledger.json"
    shutil.copyfile(ledger_path, dest)
    print(f"wrote {dest}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="teardown_ledger_gate.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("archive", cmd_archive)):
        sp = sub.add_parser(name)
        sp.add_argument("path", help="the team hub (.claude/team-forge/<team>/) or the repo root")
        sp.add_argument("--team", help="team name; required only when the repo holds more than one")
        sp.set_defaults(fn=fn)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
