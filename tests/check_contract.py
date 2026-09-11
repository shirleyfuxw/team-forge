#!/usr/bin/env python3
"""Contract-quality check — the elicitation half of the harness (GOAL.md).

check_dashboard.py verifies EMISSION (forged files render correctly); this verifies
the pivot's core deliverable: a contract whose every done_when entry the model can
check without the user. Asserts the good fixture passes clean, and that the bad
fixture fails for each seeded defect (prose entry, restated check, human-activity
check, missing decision split, bogus route, execution-steps block). Also asserts
`tools/goal_condition.py` renders the good fixture as a complete, in-cap `/goal` line.

Usage:  python3 tests/check_contract.py
Exit 0 = all green; exit 1 = the lint's bar has drifted.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from contract_lint import validate_contract, goal_directive_from_contract  # noqa: E402
from verify_contract import checklist, render  # noqa: E402
from goal_condition import goal_condition, GOAL_MAX_CHARS  # noqa: E402

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip3 install pyyaml")
    sys.exit(1)


def load(name):
    return yaml.safe_load((REPO / "tests" / "fixtures" / name).read_text())


def main():
    good = load("contract-good.yaml")
    errs = validate_contract(good)
    assert not errs, "contract-good.yaml should pass clean:\n  " + "\n  ".join(errs)
    directive = goal_directive_from_contract(good)
    assert directive["statement"].strip() and len(directive["done_when"]) == 2
    assert all("[check: " in s for s in directive["done_when"]), \
        "derived goal directive must carry the checks"
    print(f"✓ contract-good.yaml: valid · {len(good['done_when'])} checkable done_when · "
          f"derived goal directive OK")

    # The CLOSE half: the lint proves a check is runnable, this proves none was skipped when
    # the time came to run it. Direct-execution has no ledger and no gates, so this enumerator
    # is the only thing standing between "wrote checks" and "verified".
    items = checklist(good)
    assert len(items) == len(good["done_when"]), "checklist dropped a done_when entry"
    assert all(i["signal"] and i["check"] for i in items), "checklist lost a signal or check"
    assert [i["n"] for i in items] == list(range(1, len(items) + 1)), "checklist is not ordered"

    lines, ok = render(good)
    body = "\n".join(lines)
    assert not ok, "contract-good has an open_item — closing it is a user call, not automatic"
    assert "open_item" in body and "the call is theirs" in body, \
        "unresolved open_items must be surfaced to the user, not swallowed"
    for e in good["done_when"]:
        assert e["check"] in body, "every check must reach the model verbatim"

    clean = {k: v for k, v in good.items() if k != "open_items"}
    lines, ok = render(clean)
    assert ok, "a contract with no open_items and complete checks must be closeable"

    _, ok = render({"problem": {"statement": "x"}, "done_when": []})
    assert not ok, "a contract with no exit criteria must never report closeable"
    print(f"✓ verify_contract.py: enumerates {len(items)} condition(s) verbatim · "
          f"open_items block an unattended close · empty done_when rejected")

    bad_errs = validate_contract(load("contract-bad.yaml"))
    expected_fragments = [
        "prose entry",            # bare-string done_when
        "restates the signal",    # check == signal
        "human activity",         # manual-review check
        "lead_decides missing",   # decision split absent
        "user_decides missing",
        "route 'quick-pass' invalid",
        "tasks present",          # the path, frozen into the goal
    ]
    for frag in expected_fragments:
        assert any(frag in e for e in bad_errs), \
            f"contract-bad.yaml: expected an error containing {frag!r}; got:\n  " + "\n  ".join(bad_errs)
    print(f"✓ contract-bad.yaml: rejected with {len(bad_errs)} errors, "
          f"all {len(expected_fragments)} seeded defects named")

    # The contract is a goal, not a plan: EVERY path-shaped key is rejected on an otherwise
    # valid contract, so a good contract cannot smuggle steps in under a different name.
    for key in ("tasks", "steps", "plan", "milestones"):
        with_path = dict(good, **{key: [{"id": "t1", "output": "x"}]})
        errs = validate_contract(with_path)
        assert any(f"{key} present" in e for e in errs), \
            f"a valid contract with a {key!r} block must be rejected; got: {errs}"
    print("✓ execution-steps keys (tasks/steps/plan/milestones) rejected on an otherwise valid contract")

    # The /goal hand-off: the contract rendered as the harness's own stop condition. The
    # evaluator only sees the transcript, so the line must (a) name the enumerator, (b) carry
    # every signal AND check verbatim — a dropped entry is a goal that claims done early —
    # (c) turn user_decides into a pause clause and open_items into an out-of-scope clause,
    # and (d) fit the harness's cap. Never truncate: refusing is the only honest failure.
    line = goal_condition(good, "docs/team-forge/x/contract.yaml", turns=30)
    assert line.startswith("/goal "), "must be a paste-ready /goal line"
    assert "verify_contract.py docs/team-forge/x/contract.yaml" in line, "must name the enumerator"
    for e in good["done_when"]:
        assert e["signal"] in line and e["check"] in line, "every signal+check must reach the goal verbatim"
    for u in good["user_decides"]:
        assert u in line and "Pause and ask the user before" in line, "user_decides must become a pause clause"
    assert "Out of scope for this goal" in line and "exporter v1" in line, "open_items must be declared out of scope"
    assert "stop after 30 turns" in line and "stop after" not in goal_condition(good, "c.yaml", turns=0), \
        "turn bound present by default, absent at --turns 0"
    assert len(line) <= GOAL_MAX_CHARS
    try:
        goal_condition(load("contract-bad.yaml"), "c.yaml")
        raise AssertionError("an invalid contract must not render a /goal line")
    except ValueError as e:
        assert "contract invalid" in str(e)
    huge = dict(good, done_when=[{"signal": f"s{i} " + "x" * 60, "check": "y" * 60} for i in range(40)])
    try:
        goal_condition(huge, "c.yaml")
        raise AssertionError("an over-cap condition must be refused, not truncated")
    except ValueError as e:
        assert "caps it at" in str(e) and "do not truncate" in str(e)
    print(f"✓ goal_condition.py: paste-ready /goal line · every signal+check verbatim · "
          f"pause + out-of-scope clauses · invalid and over-cap contracts refused ({len(line)} chars)")

    assert validate_contract("not a mapping") == ["contract is not a mapping"]
    print("\nALL CONTRACT CHECKS PASSED")


if __name__ == "__main__":
    main()
