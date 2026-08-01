#!/usr/bin/env python3
"""Contract validator — the quality bar for the pivot's core deliverable (GOAL.md).

A contract is the user's problem + verification steps the model can run without the
user present. The load-bearing rule: every done_when entry carries a `check:` telling
the model HOW to verify (a command, a file predicate, a gate id). A condition the
model can't check isn't a verification step yet — it belongs in `open_items`.

Importable (`validate_contract(dict) -> [errors]`) so forge.py and the harness share
one bar; runnable (`python3 contract_lint.py <contract.yaml>`) for hand checks.
"""
import sys

# Checks that name a human activity instead of a mechanical step are prose in disguise.
_UNCHECKABLE = ("tbd", "todo", "manual", "eyeball", "ask the user", "user confirms",
                "looks good", "seems", "by hand")

_ROUTES = ("direct-execution", "machinery")


def validate_contract(c):
    """Return a list of error strings; empty list = valid."""
    errs = []
    if not isinstance(c, dict):
        return ["contract is not a mapping"]

    problem = c.get("problem") or {}
    if not (isinstance(problem, dict) and (problem.get("statement") or "").strip()):
        errs.append("problem.statement missing/empty — state the problem, not the first task")

    dw = c.get("done_when")
    if not (isinstance(dw, list) and dw):
        errs.append("done_when missing/empty — the contract has no exit criteria")
    else:
        for i, entry in enumerate(dw):
            where = f"done_when[{i}]"
            if not isinstance(entry, dict):
                errs.append(f"{where}: prose entry ({str(entry)[:60]!r}) — write it as "
                            "{signal, check}; if it can't be checked yet, move it to open_items")
                continue
            if not (entry.get("signal") or "").strip():
                errs.append(f"{where}: signal missing/empty")
            chk = (entry.get("check") or "").strip()
            if not chk:
                errs.append(f"{where}: check missing/empty — HOW does the model verify this "
                            "without the user? (command / file predicate / gate id)")
            elif chk.lower() == (entry.get("signal") or "").strip().lower():
                errs.append(f"{where}: check merely restates the signal — name the mechanical step")
            elif any(t in chk.lower() for t in _UNCHECKABLE):
                errs.append(f"{where}: check {chk!r} names a human activity — the model must be "
                            "able to run it; move the condition to open_items until it's checkable")

    oi = c.get("open_items")
    if oi is not None and not isinstance(oi, list):
        errs.append("open_items must be a list")

    for key in ("lead_decides", "user_decides"):
        if key not in c:
            errs.append(f"{key} missing — the decision split is part of the contract "
                        "(empty list is fine; absence is not)")
        elif not isinstance(c[key], list):
            errs.append(f"{key} must be a list")

    route = c.get("route")
    if route is not None and route not in _ROUTES:
        errs.append(f"route {route!r} invalid — one of {_ROUTES}")

    return errs


def goal_directive_from_contract(c):
    """The design.yaml/status.json goal-directive shape, derived from a contract —
    signals flatten to strings; checks ride along for the dashboard + gates."""
    return {
        "statement": c["problem"]["statement"],
        "done_when": [f"{e['signal']} [check: {e['check']}]" for e in c["done_when"]],
        "lead_decides": c.get("lead_decides") or [],
        "user_decides": c.get("user_decides") or [],
    }


def main():
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed. Run: pip3 install pyyaml")
        return 1
    if len(sys.argv) != 2:
        print("Usage: python3 contract_lint.py <contract.yaml>")
        return 2
    with open(sys.argv[1]) as f:
        errs = validate_contract(yaml.safe_load(f))
    for e in errs:
        print(f"✗ {e}")
    if not errs:
        print("✓ contract valid — every done_when entry is model-checkable")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
