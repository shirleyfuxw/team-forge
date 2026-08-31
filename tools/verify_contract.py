#!/usr/bin/env python3
"""Contract verification enumerator — the CLOSE of a team-forge engagement.

`contract_lint.py` proves every done_when entry carries a check the model *could* run.
This proves nothing was skipped when the time came to run them. Different jobs: the lint
is the bar for writing a contract, this is the checklist for closing one out.

It does NOT execute the checks. A `check:` is a description of a mechanical step, not a
shell line — `"gate `parity`: run tools/parity_check.py — exit 0, max_diff == 0"` is a
valid, well-formed check and is not a command. The model runs each one and reports the
verdict; this tool guarantees the model sees the complete list, in order, with nothing
quietly dropped, and that unresolved open_items surface instead of passing silently.

Importable (`checklist(dict) -> [entries]`) and runnable:
    python3 verify_contract.py <contract.yaml>
Exit 0 = every condition is enumerable and nothing needs the user (safe to close unattended).
Exit 1 = the close needs a human call — open_items remain, a check is missing, or the
contract has no exit criteria at all. Not a failure: a signal that closing is the user's
decision, consistent with the contract being theirs to own.
"""
import sys


def checklist(c):
    """[{n, signal, check}] for every done_when entry, in contract order."""
    return [{'n': i + 1,
             'signal': (e.get('signal') or '').strip() if isinstance(e, dict) else str(e),
             'check': (e.get('check') or '').strip() if isinstance(e, dict) else ''}
            for i, e in enumerate(c.get('done_when') or [])]


def render(c):
    """The close checklist plus any blockers. Returns (lines, ok)."""
    items, open_items = checklist(c), (c.get('open_items') or [])
    lines, ok = [], True

    statement = ((c.get('problem') or {}).get('statement') or '').strip()
    if statement:
        lines.append(f"Contract: {statement.splitlines()[0]}")
    lines.append("")

    if not items:
        lines.append("✗ no done_when entries — this contract has no exit criteria to verify")
        return lines, False

    lines.append(f"Run each check, then report ✓/✗ against it. {len(items)} condition(s):")
    for it in items:
        lines.append(f"  [ ] {it['n']}. {it['signal']}")
        lines.append(f"         check: {it['check'] or '(MISSING — run contract_lint.py)'}")
        if not it['check']:
            ok = False

    if open_items:
        ok = False
        lines.append("")
        lines.append(f"⚠ {len(open_items)} open_item(s) — conditions this contract could not make "
                     "checkable. Surface each to the user before closing; the call is theirs "
                     "(resolve, make checkable, or accept as out of scope):")
        for o in open_items:
            lines.append(f"  – {str(o).strip().splitlines()[0]}")

    lines.append("")
    lines.append("Not done until every box is ✓. A red check is not done; it is the next task."
                 if ok else "Not closeable unattended — the items above need the user.")
    return lines, ok


def main():
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed. Run: pip3 install pyyaml")
        return 1
    if len(sys.argv) != 2:
        print("Usage: python3 verify_contract.py <contract.yaml>")
        return 2
    with open(sys.argv[1]) as f:
        lines, ok = render(yaml.safe_load(f))
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
