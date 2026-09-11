#!/usr/bin/env python3
"""Render a contract as a Claude Code `/goal` condition — the harness holds the session to it.

The contract skill ends by handing the user one line to paste. `/goal <condition>` installs a
session-scoped evaluator (a separate small model) that re-checks the condition after every
turn and keeps Claude working until it holds, survives `--resume`, and runs unattended in
auto mode. Only the user can set it — it is a harness command, not a tool the model can call
— so the skill's job is to make the line correct and ready, not to set it.

The evaluator reads ONLY what Claude surfaces in the conversation; it runs no commands. So
the condition names the enumerator and demands the evidence in the transcript: every
done_when check run, its output shown. That is the contract's close (skill Step 7) restated
as a stop condition. user_decides becomes a pause clause; open_items are declared out of
scope so a goal never quietly claims a condition the contract could not make checkable.

Importable (`goal_condition(dict, contract_path, turns) -> str`) and runnable:
    python3 goal_condition.py <contract.yaml> [--turns N]
Prints the `/goal` line. Exit 1 if the contract is invalid or the line exceeds the harness's
4,000-character cap (trim signals/checks in the contract; do not truncate the condition).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract_lint import validate_contract  # noqa: E402

GOAL_MAX_CHARS = 4000     # Claude Code's cap on a /goal condition
DEFAULT_TURNS = 30        # the docs recommend a turn clause so an unattended goal is bounded

VERIFY_TOOL = Path(__file__).resolve().parent / "verify_contract.py"


def _one_line(s):
    return " ".join(str(s).split())


def goal_condition(c, contract_path, turns=DEFAULT_TURNS, verify_tool=VERIFY_TOOL):
    """The `/goal` line for a valid contract. Raises ValueError on an invalid contract or an
    over-long condition — never truncates, because a truncated condition silently drops a
    done_when entry, which is the one failure this whole file exists to prevent."""
    errs = validate_contract(c)
    if errs:
        raise ValueError("contract invalid (tools/contract_lint.py):\n  " + "\n  ".join(errs))

    contract_path = str(contract_path)
    parts = [
        f"Contract {contract_path} is verified: run `python3 {verify_tool} {contract_path}`, "
        f"then run every listed check and show each command and its output in the "
        f"conversation. All of these hold:"
    ]
    for i, e in enumerate(c["done_when"], 1):
        parts.append(f"({i}) {_one_line(e['signal'])} — check: {_one_line(e['check'])}.")

    ud = [_one_line(x) for x in (c.get("user_decides") or [])]
    if ud:
        parts.append("Pause and ask the user before: " + "; ".join(ud) + ".")

    oi = [_one_line(x) for x in (c.get("open_items") or [])]
    if oi:
        parts.append("Out of scope for this goal (open_items — surface, do not attempt to close): "
                     + "; ".join(oi) + ".")

    parts.append("Do not report done on 'looks right'; a red check is the next task.")
    if turns:
        parts.append(f"Or stop after {int(turns)} turns and report which checks still fail.")

    cond = " ".join(parts)
    if len(cond) > GOAL_MAX_CHARS:
        raise ValueError(f"/goal condition is {len(cond)} chars; the harness caps it at "
                         f"{GOAL_MAX_CHARS}. Tighten signals/checks in the contract — "
                         f"do not truncate the condition, that drops a done_when entry.")
    return "/goal " + cond


def main():
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed. Run: pip3 install pyyaml")
        return 1
    args = sys.argv[1:]
    turns = DEFAULT_TURNS
    if "--turns" in args:
        i = args.index("--turns")
        try:
            turns = int(args[i + 1])
        except (IndexError, ValueError):
            print("Usage: python3 goal_condition.py <contract.yaml> [--turns N]  (N=0 for no bound)")
            return 2
        del args[i:i + 2]
    if len(args) != 1:
        print("Usage: python3 goal_condition.py <contract.yaml> [--turns N]  (N=0 for no bound)")
        return 2
    path = Path(args[0])
    with open(path) as f:
        c = yaml.safe_load(f)
    try:
        print(goal_condition(c, path, turns))
    except ValueError as e:
        print(f"✗ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
