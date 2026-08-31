#!/usr/bin/env python3
"""Dashboard contract check for both forge archetypes.

Forges each fixture with tools/forge.py, then asserts the emitted dashboard.html is a
self-contained, interactive, single-file explorer:
  - no leftover {{SLOT}} template markers
  - the payload is embedded as `const DASHBOARD_DATA = {...}` and parses as JSON
  - the payload carries meta.team + a non-empty panels list
  - no external resource references (must work offline / from file://)
  - the inline <script> passes `node --check` when node is available (optional)

Usage:  python3 tests/check_dashboard.py
Exit 0 = all green; exit 1 = a contract violation.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORGE = REPO / "tools" / "forge.py"

# fixture design.yaml → emitted dashboard.html (target_repo is encoded in each fixture)
FIXTURES = [
    ("team-greeter", "/tmp/test-team-forge-greeter/.claude/team-forge/greeter/playground/dashboard.html"),
    ("workflow-tidy", "/tmp/test-team-forge-tidy/.claude/team-forge/tidy/playground/dashboard.html"),
    ("workflow-drain", "/tmp/test-team-forge-drain/.claude/team-forge/drain/playground/dashboard.html"),
]

NODE = shutil.which("node")


def forge(fixture):
    design = REPO / "tests" / "fixtures" / fixture / "design.yaml"
    # --force: fixtures re-forge into the same /tmp hubs every run, so the second run would
    # otherwise trip the re-forge guard. Exercises the flag as a side effect.
    r = subprocess.run([sys.executable, str(FORGE), str(design), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"{fixture}: forge failed\n{r.stdout}\n{r.stderr}"


def extract_payload(html):
    for line in html.splitlines():
        s = line.strip()
        if s.startswith("const DASHBOARD_DATA ="):
            body = s[len("const DASHBOARD_DATA ="):].strip().rstrip(";").strip()
            return json.loads(body)  # json.loads decodes the < escaping
    raise AssertionError("no `const DASHBOARD_DATA =` line found")


def check(fixture, dash_path):
    p = Path(dash_path)
    assert p.exists(), f"{fixture}: dashboard not emitted at {dash_path}"
    html = p.read_text()

    leftover = re.findall(r"\{\{[A-Z_]+\}\}", html)
    assert not leftover, f"{fixture}: leftover template slots {leftover}"

    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://', html) + re.findall(r"https?://\S+\.(?:js|css)", html)
    assert not ext, f"{fixture}: external resource refs {ext}"

    payload = extract_payload(html)
    assert payload.get("meta", {}).get("team"), f"{fixture}: payload missing meta.team"
    assert payload.get("panels"), f"{fixture}: payload missing panels"

    if NODE:
        m = re.search(r"<script>(.*)</script>", html, re.S)
        assert m, f"{fixture}: no inline <script>"
        tmp = Path("/tmp") / f"tf-check-{fixture}.js"
        tmp.write_text(m.group(1))
        r = subprocess.run([NODE, "--check", str(tmp)], capture_output=True, text=True)
        assert r.returncode == 0, f"{fixture}: inline JS syntax error\n{r.stderr}"

    extra = "" if NODE else " (node absent — skipped JS syntax check)"
    print(f"✓ {fixture}: {len(html)} bytes · self-contained · {len(payload['panels'])} panels · "
          f"archetype={payload['meta'].get('archetype')}{extra}")

    # Contract wiring (GOAL.md pivot): every fixture declares a contract, so the
    # forged ledger's goal directive must be contract-derived (checks ride along)
    # and the KB must hold the stashed copy.
    hub = p.parents[1]
    status = json.loads((hub / "tracker" / "status.json").read_text())
    directive = status.get("goal_directive") or {}
    assert directive.get("statement"), f"{fixture}: status.json missing goal_directive.statement"
    assert directive.get("done_when") and all("[check: " in s for s in directive["done_when"]), \
        f"{fixture}: goal_directive.done_when not contract-derived (no [check: ...] markers)"
    repo_root = hub.parents[2]
    assert (repo_root / "docs" / "team-forge" / hub.name / "contract.yaml").exists(), \
        f"{fixture}: contract.yaml not stashed in the KB"
    print(f"   contract-derived goal directive · {len(directive['done_when'])} checkable signals · KB copy present")

    # The shell must carry the contract strip (the payload's goal section renders above panels).
    assert 'id="contract"' in html, f"{fixture}: dashboard shell missing the contract strip mount"
    assert (payload.get("goal") or {}).get("statement"), f"{fixture}: dashboard payload missing goal section"

    # The emitted launcher is a THIN pointer to team-forge:run — never a fat baked copy.
    suffix = "team" if payload["meta"].get("archetype") == "team" else "workflow"
    launcher = repo_root / ".claude" / "skills" / f"{hub.name}-{suffix}" / "SKILL.md"
    ltext = launcher.read_text()
    assert "team-forge:run" in ltext, f"{fixture}: launcher is not a runtime pointer"
    assert len(ltext.splitlines()) < 40, f"{fixture}: launcher is fat ({len(ltext.splitlines())} lines) — policy belongs in team-forge:run"
    print(f"   contract strip in shell · thin pointer launcher ({len(ltext.splitlines())} lines)")


def check_one_shot_default_no_dashboard():
    """A one-shot workflow (recurring absent, no ledger.dashboard opt-in) must NOT emit a
    dashboard — status.json + TASKS.yaml is the ledger. Derived from workflow-tidy with
    the opt-in flag stripped."""
    import yaml
    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["ledger"].pop("dashboard", None)
    design["contract"] = str(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml")
    design["project"]["target_repo"] = "/tmp/test-team-forge-tidy-nodash"
    Path("/tmp/test-team-forge-tidy-nodash").mkdir(exist_ok=True)
    tmp_design = Path("/tmp/tf-tidy-nodash-design.yaml")
    tmp_design.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"one-shot-no-dashboard: forge failed\n{r.stdout}\n{r.stderr}"
    pg = Path("/tmp/test-team-forge-tidy-nodash/.claude/team-forge/tidy/playground")
    assert not (pg / "dashboard.html").exists(), "one-shot workflow emitted a dashboard without opt-in"
    assert not (pg / "gen_dashboard.py").exists(), "one-shot workflow emitted gen_dashboard.py without opt-in"
    print("✓ one-shot workflow without ledger.dashboard: no dashboard emitted (ledger-only)")


def check_prose_panel_rejected():
    """A dashboard_panels entry that isn't a renderer id must abort the forge — prose
    panel names shipped a silently-empty dashboard in the AOC run."""
    import yaml
    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["ledger"]["dashboard"] = True
    design["ledger"]["dashboard_panels"] = ["Issues resolved / 22 (stacked by reuse)", "task_timeline"]
    design["contract"] = str(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml")
    design["project"]["target_repo"] = "/tmp/test-team-forge-tidy-badpanel"
    Path("/tmp/test-team-forge-tidy-badpanel").mkdir(exist_ok=True)
    tmp_design = Path("/tmp/tf-tidy-badpanel-design.yaml")
    tmp_design.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design)], capture_output=True, text=True)
    assert r.returncode != 0, "forge accepted a prose dashboard_panels entry — must abort"
    assert "dashboard_panels" in (r.stdout + r.stderr), "abort message should name dashboard_panels"
    print("✓ prose dashboard_panels entry rejected at forge time")


def check_protected_branch_abort():
    """Forge must abort BEFORE emission when the target repo sits on a protected default
    branch (pre-flight absorbed from the retired forge skill)."""
    import yaml
    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["contract"] = str(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml")
    target = Path("/tmp/tf-protected-target")
    if not (target / ".git").exists():
        target.mkdir(exist_ok=True)
        subprocess.run(["git", "-C", str(target), "init", "-q", "-b", "main"], check=True)
    design["project"]["target_repo"] = str(target)
    tmp_design = Path("/tmp/tf-protected-design.yaml")
    tmp_design.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design)], capture_output=True, text=True)
    assert r.returncode != 0, "forge proceeded on a protected default branch — pre-flight missing"
    assert "main" in (r.stdout + r.stderr) and "branch" in (r.stdout + r.stderr).lower(), \
        "protected-branch abort should name the branch"
    assert not (target / ".claude").exists(), "pre-flight must abort BEFORE any emission"
    print("✓ protected-branch target: forge aborts before emission")


def check_reforge_guard_protects_ledger():
    """A bare re-forge over an already-forged hub must REFUSE. A full forge rewrites every
    output unconditionally, including tracker/status.json — which is reseeded to its initial
    state, silently destroying live task progress, gate results, and events. --force is the
    deliberate override."""
    import yaml
    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["contract"] = str(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml")
    target = Path("/tmp/test-team-forge-tidy-reforge")
    design["project"]["target_repo"] = str(target)
    target.mkdir(exist_ok=True)
    tmp_design = Path("/tmp/tf-tidy-reforge-design.yaml")
    tmp_design.write_text(yaml.safe_dump(design, sort_keys=False))

    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"reforge-guard: initial forge failed\n{r.stdout}\n{r.stderr}"

    ledger = target / ".claude" / "team-forge" / "tidy" / "tracker" / "status.json"
    live = json.loads(ledger.read_text())
    live["events"] = [{"kind": "gate_passed", "task": "t1"}]
    if live.get("tasks"):
        live["tasks"][0]["status"] = "done"
    ledger.write_text(json.dumps(live, indent=2))

    # Bare re-forge: refused, and the mutated ledger is untouched.
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design)], capture_output=True, text=True)
    assert r.returncode != 0, "bare re-forge over a live hub was allowed — the ledger guard is missing"
    out = r.stdout + r.stderr
    assert "--resync" in out and "--force" in out, "refusal should name --resync and --force"
    after = json.loads(ledger.read_text())
    assert after["events"] == live["events"], "refused re-forge still mutated the ledger"
    if live.get("tasks"):
        assert after["tasks"][0]["status"] == "done", "refused re-forge still reset task state"

    # --force is the deliberate override: it proceeds and reseeds.
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"--force re-forge failed\n{r.stdout}\n{r.stderr}"
    assert json.loads(ledger.read_text())["events"] == [], "--force should reseed the ledger"
    print("\u2713 re-forge over a live hub refused (ledger intact); --force overrides")
def check_hub_resolves_from_worktree():
    """The hub has ONE address, resolved from the main checkout — never from the caller's CWD.

    A linked worktree receives no gitignored files, so tracker/status.json is ABSENT there
    (not stale), and tracked hub files read back at whatever the worktree's branch committed.
    Proof: corrupt a template-derived file in the MAIN checkout, run --resync against the
    WORKTREE's copy of design.yaml, and assert the main checkout is what got repaired.

    The non-git fallback is covered by the three fixtures above: they forge into plain /tmp
    directories that are not repositories at all."""
    import yaml
    main_co, linked = Path("/tmp/tf-hub-main"), Path("/tmp/tf-hub-linked")
    for d in (linked, main_co):
        shutil.rmtree(d, ignore_errors=True)
    main_co.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(main_co), *a], check=True,
                                    capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (main_co / "README.md").write_text("scratch\n")
    git("add", "-A"); git("commit", "-qm", "init")
    git("checkout", "-q", "-b", "feature/forge")   # forge refuses a protected default branch

    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["contract"] = str(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml")
    design["project"]["target_repo"] = str(main_co)
    tmp_design = Path("/tmp/tf-hub-design.yaml")
    tmp_design.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(tmp_design), "--force"],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"hub-worktree: forge failed\n{r.stdout}\n{r.stderr}"

    git("add", "-A"); git("commit", "-qm", "forge")
    git("worktree", "add", "-q", str(linked), "-b", "wt/side")

    hub = ".claude/team-forge/tidy"
    assert (main_co / hub / "tracker" / "status.json").exists(), "main checkout lost its ledger"
    assert not (linked / hub / "tracker" / "status.json").exists(), \
        "expected the worktree to LACK the gitignored ledger — premise of this check"

    launcher = main_co / ".claude" / "skills" / "tidy-workflow" / "SKILL.md"
    launcher.write_text("CORRUPTED\n")

    # --resync against the WORKTREE's design copy must repair the MAIN checkout.
    r = subprocess.run([sys.executable, str(FORGE), str(linked / hub / "design.yaml"), "--resync"],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"hub-worktree: --resync from worktree failed\n{r.stdout}\n{r.stderr}"
    assert "team-forge:run" in launcher.read_text(), \
        "--resync from a worktree did not reach the main checkout — hub resolved to the wrong root"
    print("\u2713 hub resolves to the main checkout from inside a linked worktree")


def main():
    for fixture, dash in FIXTURES:
        forge(fixture)
        check(fixture, dash)
    check_one_shot_default_no_dashboard()
    check_prose_panel_rejected()
    check_protected_branch_abort()
    check_reforge_guard_protects_ledger()
    check_hub_resolves_from_worktree()
    print(f"\nALL DASHBOARD CHECKS PASSED ({len(FIXTURES)} fixtures + 5 negative checks)")
    # Elicitation half of the harness — contract quality (GOAL.md pivot).
    r = subprocess.run([sys.executable, str(REPO / "tests" / "check_contract.py")])
    assert r.returncode == 0, "contract checks failed"


if __name__ == "__main__":
    main()
