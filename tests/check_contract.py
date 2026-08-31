#!/usr/bin/env python3
"""Contract-quality check — the elicitation half of the harness (GOAL.md).

check_dashboard.py verifies EMISSION (forged files render correctly); this verifies
the pivot's core deliverable: a contract whose every done_when entry the model can
check without the user. Asserts the good fixture passes clean, and that the bad
fixture fails for each seeded defect (prose entry, restated check, human-activity
check, missing decision split, bogus route).

Usage:  python3 tests/check_contract.py
Exit 0 = all green; exit 1 = the lint's bar has drifted.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from contract_lint import validate_contract, goal_directive_from_contract  # noqa: E402
from verify_contract import checklist, render  # noqa: E402

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
    ]
    for frag in expected_fragments:
        assert any(frag in e for e in bad_errs), \
            f"contract-bad.yaml: expected an error containing {frag!r}; got:\n  " + "\n  ".join(bad_errs)
    print(f"✓ contract-bad.yaml: rejected with {len(bad_errs)} errors, "
          f"all {len(expected_fragments)} seeded defects named")

    assert validate_contract("not a mapping") == ["contract is not a mapping"]
    print("\nALL CONTRACT CHECKS PASSED")


if __name__ == "__main__":
    main()
