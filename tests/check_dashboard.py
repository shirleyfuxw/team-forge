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
    r = subprocess.run([sys.executable, str(FORGE), str(design)], capture_output=True, text=True)
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


def main():
    for fixture, dash in FIXTURES:
        forge(fixture)
        check(fixture, dash)
    print(f"\nALL DASHBOARD CHECKS PASSED ({len(FIXTURES)} fixtures)")


if __name__ == "__main__":
    main()
