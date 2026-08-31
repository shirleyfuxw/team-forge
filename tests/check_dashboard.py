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
import yaml
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

    # Settled decision 3: status.json is the single runtime surface. TASKS.yaml is a derived
    # artifact for humans — nothing emitted may send the runtime there for facts, or the
    # runtime is back to reading a copy a branch or worktree can silently disagree with.
    assert "TASKS.yaml" not in ltext, \
        f"{fixture}: launcher still points the runtime at TASKS.yaml (settled decision 3)"
    assert "status.json" in ltext, f"{fixture}: launcher does not name the runtime surface"
    agents = sorted((repo_root / ".claude" / "agents").glob(f"{hub.name}-*.md"))
    assert agents, f"{fixture}: no forged agents found"
    for prof in agents:
        ptext = prof.read_text()
        assert "TASKS.yaml" not in ptext, \
            f"{fixture}: {prof.name} still points a dispatched agent at TASKS.yaml"
        # Containment: `description` is the delegation surface a main session matches on —
        # the body's "dormant until dispatched" never enters that decision. A forged agent
        # must read as team-bound there, or it sits in every session in the repo looking like
        # a general-purpose offer.
        desc = ptext.split("---")[1].split("description:")[1].split("\nmodel:")[0]
        assert hub.name in desc, \
            f"{fixture}: {prof.name} description is not team-bound — it reads as general-purpose"
        assert "team-forge:run" in desc, \
            f"{fixture}: {prof.name} description does not say who dispatches it"
    print(f"   contract strip in shell · thin pointer launcher ({len(ltext.splitlines())} lines) · "
          f"runtime reads status.json only")


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


def check_design_drift_propagates():
    """A design.yaml change must REACH a forged team, and --check must SAY so.

    This is issue #36: --resync could only ever see template drift, so it printed
    "already current" at a team whose gate list was materially behind its own design.
    Now TASKS.yaml is derived (regenerated) and the ledger's design-derived `plan` block is
    re-baked, while every live sibling key is preserved."""
    import yaml
    target = Path("/tmp/tf-drift-main")
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(target), *a], check=True,
                                    capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (target / "README.md").write_text("scratch\n")
    git("add", "-A"); git("commit", "-qm", "init")
    git("checkout", "-q", "-b", "feature/forge")

    fx = REPO / "tests" / "fixtures" / "workflow-drain"
    design = yaml.safe_load((fx / "design.yaml").read_text())
    design["contract"] = str(fx / "contract.yaml")
    design["project"]["target_repo"] = str(target)
    dpath = Path("/tmp/tf-drift-design.yaml")
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"drift: forge failed\n{r.stdout}\n{r.stderr}"

    hub = target / ".claude" / "team-forge" / "drain"
    ledger = hub / "tracker" / "status.json"
    n_gates = len(design["gates"])

    # live progress the lead has made since the forge
    live = json.loads(ledger.read_text())
    live["events"] = [{"kind": "cycle_started"}]
    live["current_cycle_id"] = "c-42"
    ledger.write_text(json.dumps(live, indent=2))

    # the #36 edit: a new gate and a new queue sub-block
    design["gates"]["parity"] = "run tools/parity_check.py — exit 0"
    design["queue"]["trigger"] = "label:ready"
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, f"drift: --check failed\n{r.stdout}\n{r.stderr}"
    assert "already current" not in r.stdout, \
        "--check reported a false clean against a design-stale team (#36)"
    assert "parity" in r.stdout and "trigger" in r.stdout, \
        f"--check must NAME the drift, not just flag it:\n{r.stdout}"

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--resync"], capture_output=True, text=True)
    assert r.returncode == 0, f"drift: --resync failed\n{r.stdout}\n{r.stderr}"

    after = json.loads(ledger.read_text())
    assert len(after["plan"]["gates"]) == n_gates + 1, "ledger plan.gates did not pick up the new gate"
    assert "trigger" in after["plan"]["queue"], "ledger plan.queue did not pick up the new key"
    assert after["events"] == [{"kind": "cycle_started"}], "--resync clobbered live events"
    assert after["current_cycle_id"] == "c-42", "--resync clobbered live state"

    tasks_doc = yaml.safe_load((hub / "TASKS.yaml").read_text())
    assert len(tasks_doc["gates"]) == n_gates + 1, "TASKS.yaml is still stale — it is derived now"

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--check"], capture_output=True, text=True)
    assert "already current" in r.stdout, \
        f"the drift signal never clears after --resync:\n{r.stdout}"
    print("\u2713 design drift reaches the team: --check names it, --resync lands it, live state survives")


def _scratch_repo(path):
    """A throwaway git repo on a non-protected branch (forge refuses main/master/production)."""
    target = Path(path)
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(target), *a], check=True,
                                    capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (target / "README.md").write_text("scratch\n")
    git("add", "-A"); git("commit", "-qm", "init")
    git("checkout", "-q", "-b", "feature/forge")
    return target


def check_sync_goal_reaches_live_ledger():
    """A revised contract must reach a RUNNING team's standing orders.

    team-forge:run treats status.json.goal_directive as authoritative and the contract skill
    requires it to match the contract before the first task of a revised scope runs — but
    forge.py derived it once, at initial forge, and nothing could re-derive it into a live
    ledger (--resync preserves live state; a full forge destroys it). So the runtime kept
    executing forge-time orders after every contract revision, invisibly."""
    import yaml
    target = _scratch_repo("/tmp/tf-goal-main")
    fx = REPO / "tests" / "fixtures" / "workflow-tidy"
    contract = Path("/tmp/tf-goal-contract.yaml")
    shutil.copyfile(fx / "contract.yaml", contract)
    design = yaml.safe_load((fx / "design.yaml").read_text())
    design["contract"] = str(contract)
    design["project"]["target_repo"] = str(target)
    dpath = Path("/tmp/tf-goal-design.yaml")
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"sync-goal: forge failed\n{r.stdout}\n{r.stderr}"

    ledger = target / ".claude" / "team-forge" / "tidy" / "tracker" / "status.json"
    live = json.loads(ledger.read_text())
    live["current_task"] = "t2"                       # live state that must not move
    ledger.write_text(json.dumps(live, indent=2))
    before = json.loads(ledger.read_text())
    n_before = len(before["goal_directive"]["done_when"])

    c = yaml.safe_load(contract.read_text())
    c["done_when"].append({"signal": "Deprecated exporter migrated",
                           "check": "grep -rn 'def slugify' src/exporter_v1/ returns nothing"})
    c["user_decides"].append("Whether to drop exporter v1 entirely")
    contract.write_text(yaml.safe_dump(c, sort_keys=False))

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--sync-goal"], capture_output=True, text=True)
    assert r.returncode == 0, f"--sync-goal failed\n{r.stdout}\n{r.stderr}"
    after = json.loads(ledger.read_text())
    assert len(after["goal_directive"]["done_when"]) == n_before + 1, \
        "--sync-goal did not re-derive done_when into the live ledger"
    assert "Whether to drop exporter v1 entirely" in after["goal_directive"]["user_decides"]
    assert [e for e in after["events"] if e.get("kind") == "goal_revised"], \
        "--sync-goal must log a goal_revised event"
    assert after["current_task"] == "t2", "--sync-goal touched live state beyond goal_directive"
    assert after["plan"] == before["plan"], "--sync-goal touched the plan block"

    # The ledger is not the only copy of the contract. docs/team-forge/<team>/contract.yaml is
    # what the direct-execution close enumerates (contract Step 8 -> verify_contract.py), and it
    # drifts independently — so a revision that reaches the ledger but not the KB makes the close
    # verify the OLD condition list and report all-green while a new done_when was never shown.
    kb = target / "docs" / "team-forge" / "tidy" / "contract.yaml"
    kb_after = yaml.safe_load(kb.read_text())
    assert len(kb_after["done_when"]) == n_before + 1, \
        "KB contract copy is stale after --sync-goal — the close would verify the wrong list"

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--sync-goal"], capture_output=True, text=True)
    assert "no change" in r.stdout, f"--sync-goal is not idempotent:\n{r.stdout}"
    assert len([e for e in json.loads(ledger.read_text())["events"]
                if e.get("kind") == "goal_revised"]) == 1, "idempotent run still logged an event"
    print("\u2713 --sync-goal re-derives a live ledger's standing orders, logs it, touches nothing else")


def check_kb_contract_canonical_layout_untouched():
    """The CANONICAL layout — `contract:` points at docs/team-forge/<team>/contract.yaml, which
    is where team-forge:contract writes it and what design.yaml.j2 calls typical.

    There, the KB file IS the source, so treating it as derived must be a strict no-op — the
    contract is durable KB content that teardown keeps, and the drift handling only applies when
    a design deliberately points `contract:` somewhere else.

    What this catches: a refresh that drops its same-file guard. `shutil.copyfile` raises
    SameFileError when src and dst are one file, so an unconditional copy turns the DEFAULT
    layout into a hard crash on --sync-goal. Verified as a live control, not assumed."""
    import yaml
    target = _scratch_repo("/tmp/tf-kbcanon-main")
    kb_dir = target / "docs" / "team-forge" / "tidy"
    kb_dir.mkdir(parents=True)
    kb = kb_dir / "contract.yaml"
    shutil.copyfile(REPO / "tests" / "fixtures" / "workflow-tidy" / "contract.yaml", kb)

    design = yaml.safe_load((REPO / "tests" / "fixtures" / "workflow-tidy" / "design.yaml").read_text())
    design["contract"] = str(kb)                      # canonical: the KB file IS the source
    design["project"]["target_repo"] = str(target)
    dpath = Path("/tmp/tf-kbcanon-design.yaml")
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"kb-canon: forge failed\n{r.stdout}\n{r.stderr}"

    c = yaml.safe_load(kb.read_text())
    c["done_when"].append({"signal": "extra condition", "check": "grep -c x file"})
    kb.write_text(yaml.safe_dump(c, sort_keys=False))
    edited = kb.read_text()

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--resync"], capture_output=True, text=True)
    assert r.returncode == 0, f"kb-canon: --resync failed\n{r.stdout}\n{r.stderr}"
    assert kb.read_text() == edited, \
        "--resync rewrote the KB contract when it IS the source — durable content clobbered"

    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--sync-goal"], capture_output=True, text=True)
    assert r.returncode == 0, f"kb-canon: --sync-goal failed\n{r.stdout}\n{r.stderr}"
    assert kb.read_text() == edited, "--sync-goal rewrote the KB contract when it IS the source"
    ledger = json.loads((target / ".claude" / "team-forge" / "tidy" / "tracker" / "status.json").read_text())
    assert len(ledger["goal_directive"]["done_when"]) == len(c["done_when"]), \
        "the canonical layout still has to reach the ledger"
    print("\u2713 canonical contract layout: KB file is the source and is never rewritten")


def check_skill_gap_second_pass():
    """The PRODUCT joins the second pass: an unpromoted DRAFT tracks its skill_gaps spec, a
    PROMOTED skill is human-owned and never overwritten, and gate backing is recorded so
    "gates that call an unpromoted skill fail-closed" is checkable instead of merely asserted."""
    import yaml
    target = _scratch_repo("/tmp/tf-gap-main")
    fx = REPO / "tests" / "fixtures" / "workflow-tidy"
    design = yaml.safe_load((fx / "design.yaml").read_text())
    design["contract"] = str(fx / "contract.yaml")
    design["project"]["target_repo"] = str(target)
    design["gates"]["parity"] = "gate `parity`: tools/parity_check.py — exit 0"
    design["skill_gaps"] = [{"name": "tidy-parity-check", "kind": "verification",
                             "backing": "parity",
                             "purpose": "Prove byte-identical output across the refactor.",
                             "trigger": "Use when verifying a behavior-preserving refactor.",
                             "spec": "Run the corpus before and after; diff.",
                             "acceptance": "python3 tools/parity_check.py exits 0"}]
    dpath = Path("/tmp/tf-gap-design.yaml")
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--force"], capture_output=True, text=True)
    assert r.returncode == 0, f"gap: forge failed\n{r.stdout}\n{r.stderr}"

    hub = target / ".claude" / "team-forge" / "tidy"
    ledger = hub / "tracker" / "status.json"
    draft = hub / "skill-drafts" / "tidy-parity-check" / "SKILL.md"
    plan = json.loads(ledger.read_text())["plan"]
    assert "gate_backing" in plan, \
        "ledger records no gate backing — 'unpromoted skill fails the gate closed' stays unverifiable"
    assert plan["gate_backing"]["parity"] == {"skill": "tidy-parity-check", "promoted": False}, \
        f"gate backing not recorded at forge time: {plan['gate_backing']}"

    # sharpening the spec must reach the unpromoted draft
    design["skill_gaps"][0]["acceptance"] = "tools/parity_check.py exits 0 AND max_diff == 0"
    dpath.write_text(yaml.safe_dump(design, sort_keys=False))
    assert "max_diff" not in draft.read_text()
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--resync"], capture_output=True, text=True)
    assert r.returncode == 0, f"gap: --resync failed\n{r.stdout}\n{r.stderr}"
    assert "max_diff" in draft.read_text(), "an unpromoted DRAFT did not track its skill_gaps spec"

    # promotion is human-owned: --resync must never overwrite it, and backing must flip
    promoted = target / ".claude" / "skills" / "tidy-parity-check" / "SKILL.md"
    promoted.parent.mkdir(parents=True)
    promoted.write_text("---\nname: tidy-parity-check\ndescription: HUMAN-EDITED\n---\n")
    r = subprocess.run([sys.executable, str(FORGE), str(dpath), "--resync"], capture_output=True, text=True)
    assert r.returncode == 0, f"gap: --resync after promotion failed\n{r.stdout}\n{r.stderr}"
    assert "HUMAN-EDITED" in promoted.read_text(), "--resync overwrote a promoted, human-owned skill"
    assert json.loads(ledger.read_text())["plan"]["gate_backing"]["parity"]["promoted"] is True, \
        "gate backing did not flip after promotion"
    print("\u2713 skill gaps join the second pass: drafts track the spec, promoted skills are untouched")


def main():
    for fixture, dash in FIXTURES:
        forge(fixture)
        check(fixture, dash)
    check_one_shot_default_no_dashboard()
    check_prose_panel_rejected()
    check_protected_branch_abort()
    check_reforge_guard_protects_ledger()
    check_hub_resolves_from_worktree()
    check_design_drift_propagates()
    check_sync_goal_reaches_live_ledger()
    check_kb_contract_canonical_layout_untouched()
    check_skill_gap_second_pass()
    print(f"\nALL DASHBOARD CHECKS PASSED ({len(FIXTURES)} fixtures + 9 negative checks)")
    # Elicitation half of the harness — contract quality (GOAL.md pivot).
    r = subprocess.run([sys.executable, str(REPO / "tests" / "check_contract.py")])
    assert r.returncode == 0, "contract checks failed"


if __name__ == "__main__":
    main()
