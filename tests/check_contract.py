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
