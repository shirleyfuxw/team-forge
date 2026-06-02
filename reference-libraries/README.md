# reference-libraries

Pinned manifests for external curated agent/skill corpora that team-forge's
**Phase-3 asset discovery** may consult as *prior art*.

## The model: reference, not install

These libraries are **never** vendored into this repo, and **never** installed as
active Claude Code skills/agents. That's deliberate:

- **No context overflow** — a corpus like ECC has ~180 assets. Installing them as
  active skills would flood every session. Instead, discovery reads only a
  domain-filtered slice, on demand, and adapts patterns.
- **No namespace pollution** — ECC's `code-reviewer`, `architect`, etc. never
  collide with a forged team's agents because they're never loaded as agents.
- **Pinned + reproducible** — each manifest pins a specific upstream commit.
  Discovery fetches exactly that commit into a local cache; results don't drift
  when upstream changes.

## How it's consumed

1. A project's `design.yaml` lists a library by name under `reference_libraries:`.
2. Phase-3 asset discovery resolves the name to its manifest here, fetches the
   pinned commit to `~/.cache/team-forge/<name>/<commit>/` via `tools/fetch_reference.py`
   (shallow, on-demand, cached), and reads its `agents_dir` + `skills_dir`.
3. Discovery domain-filters against the project's purpose, then proposes
   **adapt** candidates — the forge writes project-owned versions citing the source.

## Updating the pin

`.github/workflows/bump-references.yml` runs weekly: for each manifest it checks
upstream's `default_branch` HEAD and, if it differs from `pinned_commit`, opens a
PR bumping the pin. Pins move deliberately (via merged PR), never silently.

## Current libraries

| name | repo | license |
|---|---|---|
| ecc | github.com/affaan-m/ECC | MIT |
