#!/usr/bin/env python3
"""Enforces team-forge:teardown Step 1 with a real exit code, instead of a jq command an
agent types by hand and can skip or misread.

skills/teardown/SKILL.md Step 1 asks two things before Step 2 removes any worktree: that
`team-forge:evolve` has run in close mode against the final state (four conditions: an
`evolve` marker exists, its `mode` is `close`, no ledger event postdates its `last_run`,
and its `candidates` file's own `mined_at` matches with no later candidates file sitting
next to it), and that the live ledger gets copied to `docs/team-forge/<team>/final-ledger.json`
before it is gone. Both were prose; this makes each one a command with an exit code.

Usage:
  teardown_ledger_gate.py check <hub-or-repo-path> [--team NAME]
  teardown_ledger_gate.py archive <hub-or-repo-path> [--team NAME]

Exit codes (check):
  0  fresh -- evolve has run in close mode against this final state. Safe to continue.
  1  MISSING -- no evolve pass has ever stamped this hub. Run evolve (close mode) first.
  2  STALE -- last pass was cycle mode, the ledger carries events after last_run, or the
     candidates marker doesn't check out. Run evolve (close mode) first.
  3  bad usage, or the ledger/design could not be read.

Exit codes (archive):
  0  docs/team-forge/<team>/final-ledger.json written.
  1  bad usage, or no live ledger to archive.
"""

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evolve_mine import load_json, resolve_hub  # noqa: E402


def parse_ts(raw):
    # A real ledger mixes "...Z" with "...+00:00"/fractional-second timestamps in one
    # file; a plain string compare (what the Step 1 jq one-liner this replaces did) sorts
    # "." before "Z" regardless of actual chronological order. Parse to real datetimes
    # instead. A value that fails to parse returns None rather than a string that would
    # compare as smaller than everything and falsely look like it precedes last_run.
    if not raw:
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def check_freshness(ledger, repo_root):
    """The four conditions SKILL.md Step 1.1 names, in order. Returns (exit_code, message).
    Every branch that cannot fully verify freshness reports STALE rather than fresh --
    an un-verifiable ledger is a reason to run evolve again, never a green light.

    `repo_root` resolves `evolve.candidates`: evolve's own Step 8 stamps it repo-relative
    (e.g. "docs/team-forge/<team>/evolve/candidates-<date>.json"), so resolving it against
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

    return 0, f"fresh · {candidates_path} · mined_at {mined_at}"


def cmd_check(args):
    hub, repo_root, _team = resolve_hub(args.path, args.team)
    ledger_path = hub / "tracker" / "status.json"
    if not ledger_path.is_file():
        print(f"UNREADABLE -- no ledger at {ledger_path}")
        return 3
    ledger = load_json(ledger_path, "ledger")
    if not ledger:
        print(f"UNREADABLE -- {ledger_path} did not parse")
        return 3
    code, message = check_freshness(ledger, repo_root)
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
