#!/usr/bin/env python3
"""Fetch a pinned reference-library commit into a local cache, on demand.

Reads a reference-library pin manifest (reference-libraries/<name>.yaml), shallow-
fetches exactly the pinned commit into ~/.cache/team-forge/<name>/<commit>/ if not
already cached, and prints the cache path. Idempotent: a cached commit is reused.

ECC (and any reference library) is NEVER vendored into team-forge or installed as
active skills — this helper materializes the pinned corpus only when Phase-3 asset
discovery asks for it.

Usage:
    python3 tools/fetch_reference.py reference-libraries/ecc.yaml
    -> prints the cache path; discovery then reads <path>/<agents_dir> + <skills_dir>
"""
import sys, subprocess, hashlib
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def fetch(manifest_path: Path) -> Path:
    m = yaml.safe_load(manifest_path.read_text())
    name = m["name"]
    repo = m["repo"]
    commit = m["pinned_commit"]

    cache = Path.home() / ".cache" / "team-forge" / name / commit
    marker = cache / ".fetched"
    if marker.exists():
        return cache  # already cached at this exact commit

    cache.mkdir(parents=True, exist_ok=True)
    # Shallow-fetch exactly the pinned commit (no full history, no other refs).
    run(["git", "init", "-q"], cwd=cache)
    run(["git", "remote", "add", "origin", repo], cwd=cache)
    try:
        run(["git", "fetch", "-q", "--depth", "1", "origin", commit], cwd=cache)
    except subprocess.CalledProcessError:
        # Some servers disallow fetching an arbitrary SHA shallowly; fall back.
        run(["git", "fetch", "-q", "--depth", "50", "origin", m.get("default_branch", "main")], cwd=cache)
    run(["git", "checkout", "-q", commit], cwd=cache)
    marker.write_text(commit + "\n")
    return cache


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 tools/fetch_reference.py <manifest.yaml>", file=sys.stderr)
        sys.exit(1)
    mp = Path(sys.argv[1])
    if not mp.exists():
        print(f"ERROR: manifest not found: {mp}", file=sys.stderr)
        sys.exit(1)
    print(fetch(mp))
