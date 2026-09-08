#!/usr/bin/env python3
"""Evolve-miner check — the harvest half of the harness (GOAL.md).

check_dashboard.py verifies EMISSION and check_contract.py verifies ELICITATION; this
verifies HARVEST: that tools/evolve_mine.py turns a finished cycle's artifacts into
candidates whose admissible/anecdote split is the evidence bar and not the miner's mood.

Written by someone who did not write the miner, on purpose — the producer never verifies
its own output here. What it proves:
  - the positive fixture yields exactly the seven ledger signals plus the one repeated
    memory note, asserted BY SIGNAL TYPE (a total-only count passes when two signals swap)
  - the true singleton kind and the one-cycle memory note are PRESENT and inadmissible —
    missing entirely is a different bug from correctly refused, and the two must not read
    the same on the way past
  - unexercised[] names the declared-but-unlogged gate, the forged-but-silent agent and
    the never-promoted skill gap
  - the negative-control ledger admits nothing at all, which is the only thing that tells
    a working admission rule from one that admits everything
  - two runs at the same --now are byte-identical
  - lessons-good.md lints clean; lessons-bad.md (row-level defects) and
    lessons-structural-bad.md (shape defects) each fail and name every seeded defect
  - a truncated or key-missing ledger warns and still writes a document, and so does one
    that is valid JSON of the wrong TYPE (an array, a bare string)
  - the second memory rule — corroboration — is live: a note written in ONE cycle section
    that a ledger candidate independently states is admitted, and the reason names a real
    candidate id rather than the first row in the list
  - the counter rules admit a lead's hand-counted repeat and refuse an ordinary compound
    noun ('third_party_api_timeout' is not three of anything)
  - blocked->resolved pairs across the four shapes a real run logs, and refuses the three
    that look like pairs and are not — including a resolution payload of {"resolution": null}
  - a MEMORY.md with no '## ' headings warns and still surfaces its bullets
  - --memory-dir adds a root without disarming the team-prefix filter on the default one
  - a gate whose status reads 'human sign-off required' is a gate working as designed, and
    'sev1'/'sev2' stay two incidents rather than merging into a recurrence named 'sev'
  - evolve's Step 8 writes every key teardown's Step 1 reads, and both --since call sites
    spell the flag the way the miner implements it

And a meta-check, because this repo has twice shipped a check that passed while its fix was
reverted: every critical assertion above is re-run against deliberately mutated copies of
the fixtures under /tmp, and must FAIL. An assertion nobody has watched fail is a comment.

Usage:  python3 tests/check_evolve.py
Exit 0 = all green; exit 1 = the miner's evidence bar has drifted, or a check went blind.
"""
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MINER = REPO / "tools" / "evolve_mine.py"
FX = REPO / "tests" / "fixtures" / "evolve"
SIGNALS = FX / "ledger-signals.json"
CLEAN = FX / "ledger-clean.json"
PAIRING = FX / "ledger-pairing.json"
ARRAY_LEDGER = FX / "array-ledger.json"
STRING_LEDGER = FX / "string-ledger.json"
MEMORY = FX / "agent-memory"
MEMORY_CORROBORATED = FX / "agent-memory-corroborated"
MEMORY_FLAT = FX / "agent-memory-flat"

SKILLS = REPO / "skills"

# Every output lands here and the tree is cleared per run. The forge once "passed" a check
# because it re-emitted into a dirty /tmp path and a stale file kept satisfying the
# assertion; a miner that stopped writing candidates-<date>.json would pass the same way.
WORK = Path("/tmp/test-team-forge-evolve-check")
NOW = "2026-09-08T00:00:00Z"     # pinned: mined_at is stamped from it, so output is reproducible
DATE = NOW[:10]

# What ledger-signals.json + the agent-memory fixture were built to yield: one of each of the
# six admissible signals, plus the recurrence admitted by a hand-maintained payload counter
# (so 'recurrence' is 2), plus the one memory note that survived into a second cycle section.
EXPECTED_ADMISSIBLE = {
    "blocked_resolved": 1,
    "budget_attribution": 2,   # one over-target per_task line, plus the whole-run total
    "gate_failure": 1,
    "lesson_event": 1,
    "memory_note": 1,
    "policy_adopted": 1,
    "recurrence": 3,   # >=2 count, a payload field counter, and a counter stated in prose
}
EXPECTED_ANECDOTES = {"memory_note": 2, "unknown_kind": 1}

EXPECTED_UNEXERCISED = {
    ("agent", "drain-monitor"),
    ("gate", "leak_guard"),
    ("skill_gap", "queue-triage-rubric"),
}


# --------------------------------------------------------------------------- driving the CLI

def mine(ledger, tag, *, memory=True, register=None, expect_rc=0, hub=FX, since=None):
    """Run the miner as a subprocess. It is not importable in the way check_contract.py
    imports its validators — and running the real CLI is the point anyway, since the skill
    shells out to exactly this.

    `memory` is True for the default sectioned fixture, False for none, or an explicit list
    of roots — the --memory-dir cases need to name their own, and passing the flag at all is
    itself under test (see check_memory_roots)."""
    out = WORK / tag
    shutil.rmtree(out, ignore_errors=True)
    cmd = [sys.executable, str(MINER), str(hub), "--team", "drain",
           "--ledger", str(ledger), "--out", str(out), "--now", NOW]
    for d in ([MEMORY] if memory is True else list(memory or [])):
        cmd += ["--memory-dir", str(d)]
    if register:
        cmd += ["--register", str(register)]
    if since:
        cmd += ["--since", since]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == expect_rc, \
        f"miner exited {r.returncode} on {Path(ledger).name} — the evolve phase cannot run " \
        f"unattended if mining a cycle can abort it\n{r.stdout}\n{r.stderr}"
    jpath = out / f"candidates-{DATE}.json"
    assert jpath.exists(), \
        f"no candidates-{DATE}.json under {out} — the skill reads the mined document, so a " \
        f"missing file is a silently skipped evolve, not a warning"
    return json.loads(jpath.read_text()), r, out


def lint(register):
    return subprocess.run([sys.executable, str(MINER), "--lint-register", str(register)],
                          capture_output=True, text=True)


def tally(doc, admissible):
    t = {}
    for c in doc["candidates"]:
        if bool(c["admissible"]) is admissible:
            t[c["signal"]] = t.get(c["signal"], 0) + 1
    return t


def find(doc, fragment):
    return [c for c in doc["candidates"] if fragment in c["claim"]]


def word_overlap(a, b):
    """Share of the smaller word set the two strings share. A local copy on purpose: this
    file drives the miner as a subprocess and must not import it, or a miner that failed to
    parse would take the harness down with it instead of being reported."""
    wa = {w for w in re.findall(r"[a-z0-9]{4,}", str(a).lower())}
    wb = {w for w in re.findall(r"[a-z0-9]{4,}", str(b).lower())}
    return len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0


# --------------------------- the critical assertions, each callable against a mutated doc ---
# Split out so the meta-check can prove each one is capable of failing. An assertion that
# only ever runs against the fixture it was written for has never been shown to reject
# anything — the same argument the fixtures' own bad/good pairing makes.

def assert_admissible_profile(doc):
    got = tally(doc, True)
    assert got == EXPECTED_ADMISSIBLE, \
        f"admissible signals are {got}, expected {EXPECTED_ADMISSIBLE} — a signal type the " \
        f"miner stopped detecting is a lesson the next cycle silently re-learns"
    assert doc["summary"]["admissible"] == sum(EXPECTED_ADMISSIBLE.values()), \
        f"summary.admissible ({doc['summary']['admissible']}) disagrees with the candidates " \
        f"themselves — the skill reads the summary and would act on a count nothing backs"


def assert_clean_admits_nothing(doc):
    adm = [c["id"] + ":" + c["signal"] for c in doc["candidates"] if c["admissible"]]
    assert not adm, \
        f"the negative-control ledger admitted {adm} — every signal in it sits deliberately " \
        f"below the bar, so anything admitted means the bar admits everything and the " \
        f"positive fixture proves nothing"
    assert doc["summary"]["admissible"] == 0, "summary.admissible disagrees with the candidates"
    assert doc["unexercised"] == [], \
        f"the negative control declared {doc['unexercised']} unexercised, but every gate, " \
        f"agent and skill gap it declares is named by one of its events — the ablation " \
        f"queue is matching on something other than use"


def assert_unexercised_profile(doc):
    got = {(u["kind"], u["name"]) for u in doc["unexercised"]}
    assert got == EXPECTED_UNEXERCISED, \
        f"unexercised is {sorted(got)}, expected {sorted(EXPECTED_UNEXERCISED)} — machinery " \
        f"the run carried and never used is what the prune half of the doctrine acts on"
    assert all(u["reason"].strip() for u in doc["unexercised"]), \
        "an unexercised entry with no reason is an unactionable line in the ablation queue"


BAD_REGISTER_DEFECTS = [
    ("duplicate id LL-1",   "a reused id makes every citation of LL-1 ambiguous forever"),
    ("Active row LL-2",     "an Active row with no Check is an unverifiable lesson"),
    ("Superseded row LL-0", "a dead claim with no 'Died at' teaches nothing"),
    ("no version banner",   "a register with no version banner cannot date its own beliefs"),
]


def assert_bad_register_named(rc, out):
    assert rc == 1, f"lessons-bad.md exited {rc} — a linter that accepts a broken register " \
                    f"is worse than none, because the register still looks checked"
    for frag, why in BAD_REGISTER_DEFECTS:
        assert frag in out, \
            f"lessons-bad.md: no error containing {frag!r} — {why}, and a count-only " \
            f"assertion would have passed on four copies of one message. Got:\n{out}"


# The four STRUCTURAL rules — they judge the register's shape, not one row's cells, and
# every one of them is vacuous-by-construction against a well-formed file: a missing table
# has no rows to iterate, and a phantom heading leaves the file looking clean while silently
# reassigning the rows after it. references/register-format.md claimed the linter checked
# the sections all along; until these landed that sentence described nothing.
STRUCTURAL_REGISTER_DEFECTS = [
    ("starts like the candidates section",
     "a prose line wrapped onto '## Candidates' reads as a section switch — the exact bug "
     "templates/lessons.md.j2 shipped into every forged register"),
    ("missing section '## Unexercised (ablation queue)'",
     "an absent table and an empty one look identical to a row-only linter, so the prune "
     "half of the doctrine stops happening without anything going red"),
    ("Active row LL-1: 'Applied to' cell empty",
     "a lesson naming no layer:path was never applied to anything"),
    ("Active rows LL-1 and LL-2 make the same claim",
     "one lesson carried twice is two registers, disagreeing from the first supersede"),
]


def assert_structural_register_named(rc, out):
    assert rc == 1, f"lessons-structural-bad.md exited {rc} — the structural rules are the " \
                    f"ones a well-formed file can never exercise, so if they do not bite here " \
                    f"they bite nowhere"
    for frag, why in STRUCTURAL_REGISTER_DEFECTS:
        assert frag in out, \
            f"lessons-structural-bad.md: no error containing {frag!r} — {why}. Got:\n{out}"


# --------------------------------------------------- the fixes this phase bought, asserted
# Each of these defends a defect a reviewer reproduced against the real CLI. They are split
# out for the same reason as the block above: an assertion nobody has watched fail is a
# comment, and the meta-check drives every one of them into failure below.

def write_ledger(name, events, **extra):
    """A one-off probe ledger under WORK. Built here rather than checked in because these
    are single-rule probes, and check_fixtures_untouched has to keep proving that a run of
    this file changes nothing under tests/fixtures/."""
    p = WORK / "probes"
    p.mkdir(parents=True, exist_ok=True)
    path = p / name
    path.write_text(json.dumps(dict({"events": events}, **extra)))
    return path


def reason_of(doc, fragment):
    hit = find(doc, fragment)
    return hit[0]["admission_reason"] if hit else ""


# --- (a) memory corroboration ------------------------------------------------------------
# The second memory rule. It was dead code: `corroborates` keyed on the matched candidate's
# id, which is assigned long after mine_memory runs, so `c["id"] == None` compared None
# against None and returned the FIRST candidate on a match and on a miss alike — `admissible`
# collapsed to bool(repeated) and a note stating the exact claim three ledger events prove
# came back "uncorroborated". So the assertion cannot stop at "admissible": it has to read
# the reason, resolve the id it names, and check the row it points at is really the match.
CORROBORATED_NOTE = "The verify brief must be built from the diff"
UNCORROBORATED_NOTE = "Re-reading the PR description before the diff"


def assert_corroboration_live(doc):
    hit = find(doc, CORROBORATED_NOTE)
    assert hit, \
        f"the corroborated memory note is absent from the output entirely — refusing it and " \
        f"dropping it are different bugs, and only one of them is visible to a reader"
    note = hit[0]
    assert note["admissible"], \
        f"a one-cycle note that the ledger independently states was refused " \
        f"({note['admission_reason']!r}) — the repeat rule cannot admit it, so the " \
        f"corroboration branch is dead again and memory harvests into nothing"
    m = re.match(r"^corroborates ledger candidate (C-\d+) \((\w+)\)$", note["admission_reason"])
    assert m, \
        f"the note was admitted with reason {note['admission_reason']!r} — the reason must " \
        f"name the candidate it corroborates, or a reader cannot check the corroboration " \
        f"and 'corroborates a ledger candidate' is an unfalsifiable sentence"
    src = [c for c in doc["candidates"] if c["id"] == m.group(1)]
    assert src and src[0]["signal"] == m.group(2), \
        f"the reason cites {m.group(1)} ({m.group(2)}), which is not a candidate in this " \
        f"document — the id-keyed lookup that returned the first row regardless of match is back"
    assert word_overlap(src[0]["claim"], note["claim"]) >= 0.4 \
        or word_overlap(src[0]["evidence"]["excerpt"], note["claim"]) >= 0.4, \
        f"the note was matched to {m.group(1)}, which shares almost none of its words — the " \
        f"corroboration rule is pairing on position rather than on content"
    # The corroborating row cleared the bar on its own evidence. The miner does not enforce
    # this — it scans every candidate, admissible or not — so this is the fixture pinning the
    # honest case, not proof of a guard. See the note in check_negative_control.
    assert src[0]["admissible"], \
        f"{m.group(1)} is itself an anecdote, so 'corroborates a ledger candidate' promoted a " \
        f"note on the strength of evidence the miner had already refused"
    other = find(doc, UNCORROBORATED_NOTE)
    assert other and not other[0]["admissible"], \
        "the sibling note in the same file and the same cycle section was admitted — then " \
        "corroboration is matching any note against any candidate and admits everything"


# --- (b) hand-counted repeats vs ordinary compounds ---------------------------------------
# `third_party_api_timeout` was admitted once with the reason "kind names 'third'" — the
# miner asserting the lead had counted a recurrence that never happened. The rule has to keep
# admitting the shapes a lead really uses to count, or tightening it just deletes the signal.
COUNTER_KINDS_ADMITTED = [
    ("merge_before_gate_second", "kind names 'second'"),      # ordinal as the last segment
    ("third_instance_stale_queue", "kind names 'third'"),     # ordinal in front of a noun
    ("hook_block_rediscovered", "kind names 'rediscovered'"),  # a repeat word, anywhere
]
COUNTER_KINDS_REFUSED = ["third_party_api_timeout", "second_line_support_ping"]


def assert_counter_kind_bar(doc):
    for kind, why in COUNTER_KINDS_ADMITTED:
        hit = [c for c in doc["candidates"] if kind in c["claim"]]
        assert hit and hit[0]["admissible"] and why in hit[0]["admission_reason"], \
            f"'{kind}' stopped being read as a hand-counted repeat ({hit and hit[0]['admission_reason']}) " \
            f"— a lead that spells the count into the kind name has asserted recurrence as " \
            f"directly as one that writes occurrence: 2, and this is a single event the >=2 " \
            f"rule can never see"
    for kind in COUNTER_KINDS_REFUSED:
        hit = [c for c in doc["candidates"] if kind in c["claim"]]
        assert hit, f"'{kind}' vanished from the output — it is still an invented one-off kind " \
                    f"and belongs in the anecdote table"
        assert not any(c["admissible"] for c in hit), \
            f"'{kind}' was admitted as a recurrence ({[c['admission_reason'] for c in hit]}) — " \
            f"'third party' and 'second line' are ordinary English compounds and count " \
            f"nothing; a rule that reads them as tallies invents the evidence it reports"


# --- (c)(e)(f) blocked -> resolved pairing -------------------------------------------------
# Four shapes a real run logs and the first rule could not see, and three that look like
# pairs and are not. Both halves in one fixture on purpose: a pairing rule is only as good as
# the pairs it refuses, and loosening it until (a)-(c) pass is the easy way to break (d)-(e).
PAIRING_PAIRED = [
    ("t-worker", "the fixture generator writes into the repo root",
     "point the generator at /tmp",
     "the block names task=T-9 and the resolution names issue=1885 AND task=T-9; comparing "
     "each side's FIRST identity field missed every resolution written by an agent that had "
     "the ticket number to hand"),
    ("t-worker", "the migration lock is held",
     "prune the previous wave's worktree",
     "a worker blocks and the LEAD logs the unblock, which is routine; an agent-equality "
     "test lost every such pair"),
    ("t-fixture", "pre-commit secret hook flags generated fixtures",
     "generated fixtures now live under tests/fixtures/",
     "a complete, honest record that names no ticket at all — requiring an id made the "
     "best-written blocks the unpairable ones"),
    ("t-alpha", "npm install fails behind the corporate proxy",
     "set npm_config_proxy",
     "the ordinary same-agent same-issue pair, which must survive the three above"),
]
PAIRING_REFUSED = [
    ("t-beta", "the schema migration needs a column",
     "two agents blocked on different issues with a resolution for only one — pairing on "
     "proximity would hand t-beta t-alpha's workaround"),
    ("t-null", "the review gate has no reviewer seat",
     "the resolution payload is {'resolution': null}; str(payload.get(f, '')) returned the "
     "truthy 'None' and rendered as 'resolved in-run by: None'"),
]


def assert_pairing_profile(doc):
    rows = [c for c in doc["candidates"] if c["signal"] == "blocked_resolved"]
    assert len(rows) == len(PAIRING_PAIRED) + len(PAIRING_REFUSED), \
        f"{len(rows)} blocked_resolved rows, expected " \
        f"{len(PAIRING_PAIRED) + len(PAIRING_REFUSED)} — every agent_blocked must surface as " \
        f"a row whether or not it paired; a dropped block is a workaround nobody can read"
    for agent, blocker, fix, why in PAIRING_PAIRED:
        hit = [c for c in rows if c["claim"].startswith(f"{agent} blocked on {blocker}")]
        assert len(hit) == 1, f"no single row for {agent} blocked on {blocker!r}"
        assert hit[0]["admissible"], \
            f"{agent}'s block did not pair — {why}. Reason given: {hit[0]['admission_reason']!r}"
        assert fix in hit[0]["claim"], \
            f"{agent}'s row paired but lost the workaround text {fix!r} — the fix that already " \
            f"worked is the lesson; the pairing alone is just two events. Got: {hit[0]['claim']!r}"
    for agent, blocker, why in PAIRING_REFUSED:
        hit = [c for c in rows if c["claim"].startswith(f"{agent} blocked on {blocker}")]
        assert len(hit) == 1, f"no single row for {agent} blocked on {blocker!r}"
        assert not hit[0]["admissible"], \
            f"{agent}'s block was paired anyway ({hit[0]['claim']!r}) — {why}"
    for c in rows:
        assert "in-run by: None" not in c["claim"], \
            f"a JSON null rendered as the workaround text 'None' in {c['id']} — a placeholder " \
            f"read as a recorded fix is worse than no row, because it looks like evidence"


# --- (d) a ledger that is valid JSON of the wrong type -------------------------------------

def assert_nonobject_ledger(doc, r, what):
    assert "⚠" in r.stdout and "not an object" in r.stdout, \
        f"{what}: mined with no warning about the type — an operator reading '0 admissible' " \
        f"cannot tell a clean cycle from an unparsed one\n{r.stdout}"
    assert doc["schema"] == "team-forge/evolve-candidates/1", \
        f"{what}: no valid document — `ledger.get('events')` on a non-dict exited the miner " \
        f"with an AttributeError and wrote nothing, so the cycle lost its memory, budget and " \
        f"design inputs to a type error too"
    assert doc["summary"]["admissible"] == 0, \
        f"{what}: an unreadable ledger produced admissible evidence — the miner must never " \
        f"fabricate a lesson out of its own damage"


# --- (g) a MEMORY.md with no cycle headings ------------------------------------------------
FLAT_NOTES = ["Dispatching a wave of four saturates", "The plan-gate route parks an item",
              "Worktree prune has to run before"]


def assert_flat_memory(doc, stdout):
    assert "no '## <cycle-id>' headings" in stdout, \
        f"a flat MEMORY.md was mined in silence — source.memory_dirs still listed the file, " \
        f"so the document read 'nothing to learn' rather than 'not parsed'\n{stdout}"
    for frag in FLAT_NOTES:
        hit = find(doc, frag)
        assert hit, \
            f"the flat file's bullet {frag!r} surfaced nowhere — nothing instructs an agent to " \
            f"section its memory, so this is the shape most files take and dropping it loses " \
            f"the trail to every lesson they hold"
        assert not hit[0]["admissible"], \
            f"{frag!r} was admitted — one section means the cross-cycle repeat rule cannot " \
            f"have fired, so admitting it is the bar being applied to a file it cannot judge"


# --- (h) --memory-dir must not disarm the default root's team filter -----------------------

def assert_memory_roots(doc, expected, what):
    got = sorted(Path(d).name for d in doc["source"]["memory_dirs"])
    assert got == sorted(expected), \
        f"{what}: mined memory dirs {got}, expected {sorted(expected)} — the `<team>-` prefix " \
        f"filter belongs to the default root and only to it. Testing the flag's truthiness " \
        f"inside one loop over all roots dropped the filter from the default root the moment " \
        f"--memory-dir was passed, and every other team's memory landed in this team's candidates"


# --- (i) a gate working as designed is not a gate failure ----------------------------------
GATE_NOT_FAILURES = [
    ("release_signoff", "a gate whose status is 'human sign-off required' — 'red' matched as a "
                        "substring inside 'required' and filed a working gate as a failure "
                        "with action add_gate"),
    ("deferred_scan", "'deferred' likewise contains 'red'; a gate postponed on purpose is not "
                      "a gate that failed"),
]


def assert_gate_status_words(doc):
    gates = [c for c in doc["candidates"] if c["signal"] == "gate_failure"]
    for name, why in GATE_NOT_FAILURES:
        assert not [c for c in gates if name in c["claim"]], \
            f"gate '{name}' was filed as a gate failure — {why}. Rows: " \
            f"{[c['claim'] for c in gates]}"
    real = [c for c in gates if "import_check" in c["claim"]]
    assert len(real) == 1 and real[0]["admissible"] and "shadows a stdlib" in real[0]["claim"], \
        f"the genuinely failed gate stopped being mined ({[c['claim'] for c in gates]}) — " \
        f"dropping a fail word to stop a false positive is only a fix if the true positives live"


# --- (j) two incidents must not merge into one -------------------------------------------

def assert_kind_split(doc):
    assert not [c for c in doc["candidates"] if "'sev'" in c["claim"]], \
        "a candidate is filed under 'sev' — stripping digits to a fixed point merged sev1 and " \
        "sev2 into one admissible recurrence, named for a noun that appears in no event, so a " \
        "reader could not grep back to the evidence"
    for kind in ("sev1", "sev2"):
        hit = [c for c in doc["candidates"] if f"'{kind}'" in c["claim"]]
        assert len(hit) == 1 and not hit[0]["admissible"], \
            f"'{kind}' is not a single refused singleton ({[c['claim'][:60] for c in hit]}) — " \
            f"each is one sighting of one incident"
    collapsed = [c for c in doc["candidates"] if "'gate_scope_defect'" in c["claim"]
                 and c["signal"] == "recurrence"]
    assert len(collapsed) == 1 and collapsed[0]["admissible"] \
        and "logged as gate_scope_defect, gate_scope_defect_2" in collapsed[0]["claim"], \
        "the single trailing `_<n>` disambiguator stopped collapsing — refusing to normalize " \
        "at all is the other way to get this wrong: one finding logged twice reads as two " \
        "one-off nouns and neither clears the bar"


# --- the prose contract: evolve Step 8 -> teardown Step 1, and --since --------------------
# Two skills and a tool agreeing by hand. The marker teardown gates on is written by evolve
# and by nothing else, so a key renamed on one side makes teardown report "MISSING — no
# evolve pass has ever stamped this hub" forever, and the prescribed fix re-runs the pass
# that writes the same key it is not reading.

def assert_handoff_contract(evolve_text, teardown_text):
    step8 = evolve_text.split("### Step 8")[-1]
    written = set(re.findall(r'"(\w+)":', step8.split('"evolve"')[-1].split("```")[0]))
    read = set(re.findall(r"\$e\.(\w+)", teardown_text))
    assert read, "teardown Step 1 reads no `$e.<key>` at all — the freshness gate is gone"
    missing = sorted(read - written)
    assert not missing, \
        f"teardown Step 1 reads $e.{missing} and evolve's Step 8 writes {sorted(written)} — " \
        f"a key only one side knows makes the gate report MISSING on a pass that ran, and " \
        f"the prescribed fix is the pass that writes it"
    for key in ("mode", "last_run", "candidates", "mined_at"):
        assert key in written, \
            f"evolve Step 8 stopped writing `{key}` — teardown gates on mode == 'close', on " \
            f"no event later than last_run, and on candidates/mined_at agreeing with the " \
            f"mined file, so a dropped key silently opens the gate"
    assert '"mode": "close|cycle"' in step8, \
        "Step 8 no longer states the two modes teardown discriminates on"


SINCE_CALL = '--since "$(jq -r \'.current_cycle_id\' <hub>/tracker/status.json)"'


def assert_since_documented(texts):
    for name, text in texts:
        assert SINCE_CALL in text, \
            f"{name} does not invoke the miner with {SINCE_CALL} — a cycle pass without " \
            f"--since re-mines the whole ledger, so by cycle six the admissible list is the " \
            f"phase's own exhaust (every earlier `lesson` and `policy_adopted` returning as " \
            f"a fresh proposal) and the run's real evidence is buried under it"


# --------------------------------------------------------------------------- the checks

def check_positive_signals():
    doc, r, out = mine(SIGNALS, "signals")
    assert doc["schema"] == "team-forge/evolve-candidates/1", \
        f"schema is {doc['schema']!r} — the skill dispatches on it"
    assert doc["team"] == "drain" and doc["forge_version"] == "0.12.0", \
        "team/forge_version must come off the manifest; a candidate file that cannot say " \
        "which forge produced it cannot be replayed"
    assert_admissible_profile(doc)

    # The two recurrence rows are different rules wearing one signal name, so pin them apart:
    # a plain >=2 count, and the counter the lead maintained by hand on a single event.
    counted = [c for c in doc["candidates"] if c["admission_reason"].startswith("recurrence>=")]
    counter = [c for c in doc["candidates"] if "recurrence counter" in c["admission_reason"]]
    assert len(counted) == 1 and "verifier_prompt_contamination" in counted[0]["claim"], \
        "the >=2 recurrence rule stopped firing on the invented kind logged three times"
    assert len(counter) == 2, \
        "the hand-maintained payload counter stopped admitting — those cases are single " \
        "events, so the >=2 rule alone never sees them and the lead's own count is the " \
        "whole evidence"
    assert any("occurrence=2" in c["admission_reason"] for c in counter), \
        "the numeric counter field stopped admitting"
    # The same assertion written as prose. The one real ledger states its counts in the note
    # and nowhere else — "Eighth instance of tonight's proxy-substitution pattern class" on the
    # event recording a truthy-string fake-green — and a field-only rule filed the single most
    # important lesson of that run as an anecdote.
    prose = [c for c in counter if "says 'Third instance'" in c["admission_reason"]]
    assert len(prose) == 1 and prose[0]["evidence"]["count"] == 3 \
        and "stale_queue_snapshot" in prose[0]["claim"], \
        "the prose counter stopped admitting — a lead that hand-counts a repeat in the note " \
        "has asserted recurrence just as directly as one that writes occurrence: 3"

    blocked = [c for c in doc["candidates"] if c["signal"] == "blocked_resolved" and c["admissible"]][0]
    assert "/tmp" in blocked["claim"], \
        "the blocked->resolved row lost the workaround text — the fix that already worked is " \
        "the lesson; the pairing alone is just two events"

    gate = [c for c in doc["candidates"] if c["signal"] == "gate_failure" and c["admissible"]][0]
    assert "root cause" in gate["claim"] and "no Agent tool" in gate["claim"], \
        "the gate-failure row dropped its root cause, which is the only thing separating it " \
        "from a red gate nobody can act on"

    budget = [c for c in doc["candidates"] if c["signal"] == "budget_attribution" and c["admissible"]][0]
    assert "monitor dashboard renders" in budget["claim"], \
        "the wrong budget line was attributed — naming the line is what let a human cut a seat"
    assert "5.0x" in budget["admission_reason"], \
        "the budget bar is not the team's own: design.yaml sets budget_overrun_factor 5 and " \
        "the reason must say so, or the default 3 was silently used"
    assert not find(doc, "advisor-consults"), \
        "the 4.1x advisor-consults line was admitted — it sits under the team's declared 5x " \
        "bar and only clears the default 3x, so the override is being ignored"

    # The whole-run total, separately. Every per_task line of the one real overrun sat under
    # 5x while the run as a whole spent 1010% of its target; a per-line-only miner reported a
    # blip and never said the run had blown its budget by an order of magnitude.
    whole = [c for c in doc["candidates"] if "the run as a whole spent" in c["claim"]]
    assert len(whole) == 1 and whole[0]["admissible"] and "14.3x" in whole[0]["claim"], \
        "the whole-run budget line stopped being mined — budget.spent against budget.soft_target " \
        "is the number a human acts on, and no per_task line carries it"

    lesson = [c for c in doc["candidates"] if c["signal"] == "lesson_event" and c["admissible"]][0]
    assert (lesson["suggested_layer"], lesson["suggested_target"]) == ("L2", "design.yaml#worker.procedure"), \
        "a lesson event that states its own layer/target must keep them — the lead routing a " \
        "lesson by hand outranks the miner's heuristic"

    for c in doc["candidates"]:
        assert c["admission_reason"].strip(), f"{c['id']} carries no admission reason"
        assert c["evidence"]["refs"], f"{c['id']} cites no event — an unciteable row is a claim"

    md = (out / f"candidates-{DATE}.md").read_text()
    assert all(c["id"] in md for c in doc["candidates"] if c["admissible"]), \
        "the .md the skill actually reads is missing an admissible candidate the .json carries"
    print(f"✓ ledger-signals.json: {doc['summary']['admissible']} admissible, by type "
          f"{tally(doc, True)} · budget bar 5x (team override) · lead routing preserved")


def check_anecdotes_recorded():
    doc, _, _ = mine(SIGNALS, "signals-anecdotes")
    got = tally(doc, False)
    assert got == EXPECTED_ANECDOTES, \
        f"anecdotes are {got}, expected {EXPECTED_ANECDOTES} — anecdotes are RECORDED and " \
        f"never applied, so dropping one loses the trail to the lesson it later becomes"

    singleton = find(doc, "future_leak_ok_schema_gap")
    assert singleton, \
        "the one-off invented kind 'future_leak_ok_schema_gap' is absent from the output " \
        "entirely — that is a different bug from refusing it, and the register would never " \
        "learn the schema had no slot for it"
    assert not singleton[0]["admissible"], \
        "a kind invented once and never reused was admitted — acting on all ~50 of those is " \
        "how a register becomes a wall nobody reads"

    unique_note = find(doc, "Waves of four saturate")
    assert unique_note, \
        "the one-cycle memory note is absent from the output entirely — memory harvested " \
        "into nothing is the failure this phase exists to fix; refusing it is fine, dropping " \
        "it silently is not"
    assert not unique_note[0]["admissible"] and "uncorroborated" in unique_note[0]["admission_reason"], \
        "a note written once in one cycle section was admitted — one agent's one-time " \
        "observation is not evidence"

    repeated = find(doc, "Keep verifier scratch files outside")
    assert repeated and repeated[0]["admissible"], \
        "the note carried into a second cycle section was not admitted — repetition across " \
        "cycles is the whole memory rule"
    print(f"✓ anecdotes: {got} recorded not applied · singleton kind and one-cycle note both "
          f"present and refused · the twice-written note admitted")


def check_unexercised():
    doc, _, _ = mine(SIGNALS, "signals-unexercised")
    assert_unexercised_profile(doc)
    print(f"✓ unexercised: {', '.join(f'{u[0]} {u[1]}' for u in sorted(EXPECTED_UNEXERCISED))} "
          f"— declared machinery no event names")


def check_negative_control():
    doc, _, _ = mine(CLEAN, "clean", memory=False)
    assert_clean_admits_nothing(doc)
    # A miner that found nothing at all would also report zero admissible. The clean ledger
    # still invents two nouns and logs an uncommitted lesson, so it must produce anecdotes.
    # The prose-counter rule's negative control: the same "<number> times" shape used as a
    # MEASUREMENT. A rule that reads "three times slower" as three sightings would manufacture
    # a recurrence out of a benchmark, and every prose counter it admits elsewhere would be
    # unfalsifiable.
    decoy = find(doc, "differential_timing_note")
    assert decoy, "the multiplier decoy vanished from the control's output entirely"
    assert not decoy[0]["admissible"] and "no counter" in decoy[0]["admission_reason"], \
        f"'three times slower' was admitted as a recurrence ({decoy[0]['admission_reason']!r}) " \
        f"— the prose counter is reading multipliers as counts and admits anything numeric"
    assert doc["summary"]["anecdotes"] >= 3, \
        f"the negative control produced {doc['summary']['anecdotes']} anecdotes — zero " \
        f"admissible only means something when the miner is demonstrably still reading"
    print(f"✓ ledger-clean.json (negative control): 0 admissible · "
          f"{doc['summary']['anecdotes']} anecdotes still recorded · unexercised empty")


def check_determinism():
    a, _, aout = mine(SIGNALS, "det-a")
    b, _, bout = mine(SIGNALS, "det-b")
    for name in (f"candidates-{DATE}.json", f"candidates-{DATE}.md"):
        ha = hashlib.sha256((aout / name).read_bytes()).hexdigest()
        hb = hashlib.sha256((bout / name).read_bytes()).hexdigest()
        assert ha == hb, \
            f"{name} differs between two runs at the same --now — a candidate file that " \
            f"churns cannot be diffed cycle over cycle, and every evolve would look like change"
    assert a["mined_at"] == NOW, "--now must be stamped verbatim or nothing is reproducible"
    print(f"✓ determinism: two runs at --now {NOW} are byte-identical (json + md)")


def check_register_dedupe():
    doc, _, _ = mine(SIGNALS, "register", register=FX / "lessons-good.md")
    reg = doc["register"]
    assert reg["exists"] and reg["banner"] and reg["active_ids"] == ["LL-1", "LL-2"], \
        f"the register was not read: {reg}"
    assert all(not c["id"].endswith("-001") for c in doc["candidates"]), \
        "C-ids restarted at C-001 over a register that already holds C-1 — ids are " \
        "append-only, and a reused id is exactly what --lint-register rejects"
    dupes = {c["status"] for c in doc["candidates"] if c["related_lessons"]}
    assert any(s.startswith("duplicate_of:LL-") for s in dupes), \
        "no candidate matched an Active lesson — a cycle that re-proposes LL-2 every week " \
        "is how the register grows without learning anything"
    print(f"✓ register dedupe: next id {doc['candidates'][0]['id']} after C-1 · "
          f"{sum(1 for c in doc['candidates'] if c['related_lessons'])} flagged duplicate_of")


def check_register_lint():
    r = lint(FX / "lessons-good.md")
    assert r.returncode == 0, \
        f"lessons-good.md was rejected — a linter that fails valid registers gets switched " \
        f"off, and then nothing is checked at all\n{r.stdout}{r.stderr}"
    assert "register valid" in r.stdout
    print("✓ lessons-good.md: lints clean (2 active, 1 superseded, banner present)")

    r = lint(FX / "lessons-bad.md")
    assert_bad_register_named(r.returncode, r.stdout + r.stderr)
    print(f"✓ lessons-bad.md: rejected, all {len(BAD_REGISTER_DEFECTS)} seeded row-level "
          f"defects named individually")

    r = lint(FX / "lessons-structural-bad.md")
    assert_structural_register_named(r.returncode, r.stdout + r.stderr)
    print(f"✓ lessons-structural-bad.md: rejected, all {len(STRUCTURAL_REGISTER_DEFECTS)} "
          f"seeded structural defects named individually (phantom heading · missing section · "
          f"empty Applied-to · duplicate claim)")


def check_malformed_inputs():
    """A cycle killed mid-write leaves a half-written ledger. Losing the rest of that cycle's
    lessons to a JSONDecodeError is the expensive failure — the miner runs unattended."""
    bad = WORK / "malformed"
    bad.mkdir(parents=True, exist_ok=True)
    raw = SIGNALS.read_text()

    # Unreadable AS A LEDGER — the miner has nothing to mine and has to say so out loud.
    unreadable = {
        "truncated.json": raw[: len(raw) // 2],
        "no-events.json": json.dumps({"current_cycle_id": "cycle-x"}),
        "events-not-a-list.json": json.dumps({"events": {"kind": "cycle_started"}, "budget": "nope"}),
    }
    # Readable, with junk rows inside events[]. The rows are dropped rather than warned about;
    # what matters here is that none of them becomes evidence — an early miner reported two
    # kind-less events from a truncated ledger as a recurring invented kind called `none`.
    junk = {"junk-events.json": json.dumps({"events": [None, 7, {"kind": None},
                                                       {"kind": "agent_blocked", "payload": "not a dict"}]})}
    for name, body in {**unreadable, **junk}.items():
        (bad / name).write_text(body)
    unreadable["absent.json"] = None  # never written: the torn-down-run path

    # Memory is deliberately off here: it is a separate input and stays readable when the
    # ledger is not, so mining it would put an honest admissible row in the output and hide
    # whether the damaged ledger contributed one of its own.
    for name in {**unreadable, **junk}:
        doc, r, _ = mine(bad / name, f"mal-{name}", memory=False)
        assert doc["schema"] == "team-forge/evolve-candidates/1" and doc["summary"]["admissible"] == 0, \
            f"{name}: damaged input still produced admissible evidence — the miner must never " \
            f"fabricate a lesson out of its own damage"
        assert not any("'none'" in c["claim"] for c in doc["candidates"]), \
            f"{name}: a kind-less event was reported as an invented kind 'none' — that is the " \
            f"miner inventing evidence out of its own damage"
        if name in unreadable:
            assert "⚠" in r.stdout, \
                f"{name}: mined with no warning — an unreadable ledger that reports success is " \
                f"how a cycle's lessons go missing without anyone noticing"
    print(f"✓ malformed input: {len(unreadable)} unreadable ledgers warn and exit 0 · junk rows "
          f"dropped without becoming evidence · every case still writes a valid document")


def check_memory_corroboration():
    """(a) The one-cycle note the ledger independently states."""
    doc, _, _ = mine(SIGNALS, "corroborated", memory=[MEMORY_CORROBORATED])
    assert_corroboration_live(doc)
    note = find(doc, CORROBORATED_NOTE)[0]
    print(f"✓ memory corroboration: a one-cycle note admitted — {note['admission_reason']} · "
          f"the sibling note in the same section stays an anecdote")


def check_counter_kind_bar():
    """(b) A hand-counted repeat is admitted; an ordinary compound noun is not."""
    events = [{"ts": f"2026-09-01T09:0{i}:00Z", "agent": "lead", "kind": k,
               "payload": {"note": n}}
              for i, (k, n) in enumerate([
                  ("third_party_api_timeout",
                   "the vendor status endpoint timed out while the wave was draining"),
                  ("second_line_support_ping",
                   "second-line support was paged about the migration lock and never replied"),
                  ("merge_before_gate_second",
                   "a PR merged before its gate finished, for the second time this month"),
                  ("third_instance_stale_queue",
                   "the queue snapshot went stale mid-wave and the lead acted on pre-push counts"),
                  ("hook_block_rediscovered",
                   "the branch-safety hook blocked the very writes the fix stage needs"),
              ])]
    doc, _, _ = mine(write_ledger("counter-kinds.json", events), "counter-kinds", memory=False)
    assert_counter_kind_bar(doc)
    # The same trap sits in the checked-in negative control, where it has to stay refused
    # alongside everything else — a rule that only behaves in its own probe file is not a bar.
    clean, _, _ = mine(CLEAN, "counter-clean", memory=False)
    assert reason_of(clean, "third_party_api_timeout").startswith("single invented kind"), \
        f"the control's own 'third' trap came back as " \
        f"{reason_of(clean, 'third_party_api_timeout')!r}"
    print("✓ counter kinds: 3 hand-counted repeats admitted (last-segment ordinal · ordinal "
          "before an instance-noun · repeat word) · 'third party' and 'second line' refused "
          "here and in the negative control")


def check_pairing_shapes():
    """(c)(e)(f) The four blocked->resolved shapes a real run logs, and the three refusals."""
    doc, _, _ = mine(PAIRING, "pairing", memory=False)
    assert_pairing_profile(doc)
    print(f"✓ blocked->resolved: {len(PAIRING_PAIRED)} pairs found (identity by intersection · "
          f"lead logs a worker's unblock · no ticket id at all · the plain case), "
          f"{len(PAIRING_REFUSED)} refused (different issues · a null resolution)")


def check_nonobject_ledgers():
    """(d) Valid JSON that is not an object. Both shapes ship from the same accident: a
    status.json half-exported as its events array, or clobbered by a shell redirect."""
    for path, what in ((ARRAY_LEDGER, "a JSON array"), (STRING_LEDGER, "a JSON string")):
        doc, r, _ = mine(path, f"nonobject-{path.stem}", memory=False)
        assert_nonobject_ledger(doc, r, what)
    # The warning has to be about THIS damage. An object ledger emitting it too would make the
    # assertion above pass on any input at all.
    _, ok, _ = mine(SIGNALS, "nonobject-control", memory=False)
    assert "not an object" not in ok.stdout, \
        f"a well-formed ledger warns about its own type — then the warning says nothing\n{ok.stdout}"
    print("✓ non-object ledgers: an array and a bare string each warn by type and still write "
          "a valid document · a well-formed ledger stays quiet")


def check_flat_memory():
    """(g) A MEMORY.md with no '## ' headings. Native memory is self-curated and nothing tells
    an agent to section it, so this is the shape most files take."""
    doc, r, _ = mine(SIGNALS, "flat-memory", memory=[MEMORY_FLAT])
    assert_flat_memory(doc, r.stdout)
    # And the negative control holds across the memory path, not just with memory switched
    # off: the flat file's three notes corroborate nothing the clean ledger shows, so a run
    # with both inputs still admits nothing.
    clean, _, _ = mine(CLEAN, "flat-memory-clean", memory=[MEMORY_FLAT])
    assert_clean_admits_nothing(clean)
    print(f"✓ flat memory: warns and still surfaces {len(FLAT_NOTES)} bullets as anecdotes · "
          f"the negative control still admits 0 with that memory attached")


def check_memory_roots():
    """(h) --memory-dir adds a root; it does not disarm the default root's team filter."""
    root = WORK / "memroots"
    repo = root / "repo"
    hub = repo / ".claude" / "team-forge" / "drain"
    hub.mkdir(parents=True, exist_ok=True)
    for f in ("design.yaml", "manifest.json"):
        shutil.copyfile(FX / f, hub / f)
    for seat, body in (("drain-worker", "a drain seat's note about the branch-safety hook"),
                       ("other-worker", "another team's note about payment reconciliation")):
        d = repo / ".claude" / "agent-memory" / seat
        d.mkdir(parents=True, exist_ok=True)
        (d / "MEMORY.md").write_text(f"# {seat}\n\n## cycle-1\n- {body}, written down once.\n")
    picked = root / "handpicked" / "archived-verifier"     # no `<team>-` prefix, by hand
    picked.mkdir(parents=True, exist_ok=True)
    (picked / "MEMORY.md").write_text(
        "# archived\n\n## cycle-0\n- An archived seat whose directory name carries no team "
        "prefix at all.\n")

    doc, _, _ = mine(SIGNALS, "memroots-default", memory=False, hub=repo)
    assert_memory_roots(doc, ["drain-worker"], "default root alone")
    doc, _, _ = mine(SIGNALS, "memroots-extra", memory=[root / "handpicked"], hub=repo)
    assert_memory_roots(doc, ["drain-worker", "archived-verifier"], "default root + --memory-dir")
    print("✓ memory roots: the default root keeps its `drain-` filter with --memory-dir passed "
          "(other-worker excluded both times) · a hand-picked root is mined unfiltered")


def check_gate_status_words():
    """(i) A gate waiting on a human is a gate working as designed."""
    events = [
        {"ts": "2026-09-01T09:00:00Z", "agent": "lead", "kind": "ticket_gated",
         "payload": {"issue": 1, "gate": "release_signoff", "result": "human sign-off required",
                     "reason": "the release gate waits for a named human, by design"}},
        {"ts": "2026-09-01T09:01:00Z", "agent": "lead", "kind": "ticket_gated",
         "payload": {"issue": 2, "gate": "deferred_scan", "status": "deferred to next cycle",
                     "reason": "the scanner image is not built yet"}},
        {"ts": "2026-09-01T09:02:00Z", "agent": "lead", "kind": "ticket_gated",
         "payload": {"issue": 3, "gate": "import_check", "result": "failed",
                     "root_cause": "the package shadows a stdlib module name"}},
    ]
    doc, _, _ = mine(write_ledger("gate-words.json", events), "gate-words", memory=False)
    assert_gate_status_words(doc)
    # The control carries the same trap, and its whole contract is 0 admissible.
    clean, _, _ = mine(CLEAN, "gate-words-clean", memory=False)
    assert not [c for c in clean["candidates"] if c["signal"] == "gate_failure"], \
        f"the negative control produced a gate failure: " \
        f"{[c['claim'] for c in clean['candidates'] if c['signal'] == 'gate_failure']}"
    print("✓ gate status words: 'human sign-off required' and 'deferred' are not failures · a "
          "genuinely failed gate with a root cause still is · the control files none at all")


def check_kind_normalization():
    """(j) `sev1` and `sev2` are two incidents; `x` and `x_2` are one finding logged twice."""
    events = [
        {"ts": "2026-09-01T09:00:00Z", "agent": "lead", "kind": "sev1",
         "payload": {"note": "the queue drained to zero while tickets were still open"}},
        {"ts": "2026-09-01T09:01:00Z", "agent": "lead", "kind": "sev2",
         "payload": {"note": "a worker seat idled for the whole wave with nothing dispatched"}},
        {"ts": "2026-09-01T09:02:00Z", "agent": "lead", "kind": "gate_scope_defect",
         "payload": {"note": "the instrument's scope excluded the defect class it guards"}},
        {"ts": "2026-09-01T09:03:00Z", "agent": "lead", "kind": "gate_scope_defect_2",
         "payload": {"note": "the same shape on the second gate this cycle"}},
    ]
    doc, _, _ = mine(write_ledger("normalize.json", events), "normalize", memory=False)
    assert_kind_split(doc)
    print("✓ kind normalization: sev1 and sev2 stay two refused singletons · one trailing "
          "`_<n>` disambiguator still collapses gate_scope_defect + _2 into one recurrence")


def check_since_window():
    """--since is what keeps a cycle pass off its own exhaust, so both the flag and the two
    call sites that invoke it are under test."""
    full, _, _ = mine(SIGNALS, "since-none", memory=False)
    iso, r_iso, _ = mine(SIGNALS, "since-iso", memory=False, since="2026-09-01")
    assert iso["source"]["events"] < full["source"]["events"], \
        f"--since 2026-09-01 mined {iso['source']['events']} of {full['source']['events']} " \
        f"events — an ISO prefix must drop everything logged before it, or a cycle pass " \
        f"re-admits every earlier cycle's `lesson` and `policy_adopted` events"
    cyc, _, _ = mine(SIGNALS, "since-cycle", memory=False, since="cycle-2026-09-01-001")
    assert cyc["source"]["cycles"] == ["cycle-2026-09-01-001"], \
        f"--since <cycle id> resolved to {cyc['source']['cycles']} — the skill passes exactly " \
        f"`jq -r .current_cycle_id`, so a cycle id that resolves to nothing is the common case"
    junk, r_junk, _ = mine(SIGNALS, "since-junk", memory=False, since="cycle-nope")
    assert junk["source"]["events"] == full["source"]["events"] and "⚠" in r_junk.stdout, \
        f"an unresolvable --since mined {junk['source']['events']} events without warning — " \
        f"silently mining zero is how a cycle loses its lessons to a typo\n{r_junk.stdout}"
    assert_since_documented([("skills/evolve/SKILL.md", (SKILLS / "evolve" / "SKILL.md").read_text()),
                             ("skills/run/references/drain.md",
                              (SKILLS / "run" / "references" / "drain.md").read_text())])
    print("✓ --since: ISO prefix narrows the window, a cycle id resolves to that cycle, a "
          "typo warns and mines everything · both call sites spell it the way argparse takes it")


def assert_pairing_vocabulary(run_text):
    """The identity + resolution field lists in run/SKILL.md ARE the miner's constants.

    A lead reads that block to learn what to log; the miner reads the constants to decide what
    pairs. When the two drifted, the skill told leads that a block with no identity key "pairs
    with nothing" long after the miner had learned to pair it by echo — so the prose was
    actively discouraging the honest record the fix was bought to reward. Prose that documents
    behavior the code stopped having is the defect class this plugin exists to remove, and the
    only cheap defense is to pin the lists.
    """
    # Read from source rather than importing: this harness drives the miner only as a
    # subprocess, and that separation is deliberate.
    tree = ast.parse((REPO / "tools" / "evolve_mine.py").read_text())
    consts = {n.targets[0].id: ast.literal_eval(n.value)
              for n in tree.body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
              and n.targets[0].id in ("ISSUE_FIELDS", "RESOLUTION_FIELDS")}
    ISSUE_FIELDS, RESOLUTION_FIELDS = consts["ISSUE_FIELDS"], consts["RESOLUTION_FIELDS"]
    block = run_text.split("Identity fields read")[-1].split("\n\n\n")[0]
    for f in ISSUE_FIELDS:
        assert f"`{f}`" in block, \
            f"the miner pairs on identity field `{f}` and run/SKILL.md never names it — a lead " \
            f"logging it has no way to know the pair will be read"
    for f in RESOLUTION_FIELDS:
        assert f"`{f}`" in block, \
            f"the miner reads `{f}` as a resolution and run/SKILL.md never names it"
    documented = set(re.findall(r"`([a-z_]+)`", block))
    phantom = documented & {"same_agent", "issue_id"}
    assert not phantom, f"run/SKILL.md documents identity fields the miner does not read: {phantom}"


def check_pairing_vocabulary():
    assert_pairing_vocabulary((SKILLS / "run" / "SKILL.md").read_text())
    print("\u2713 pairing vocabulary: every identity and resolution field the miner pairs on is "
          "named in run/SKILL.md's ledger-vocabulary block")


def check_evolve_teardown_handoff():
    """The marker evolve stamps and teardown gates on. One writer, one reader, no schema."""
    assert_handoff_contract((SKILLS / "evolve" / "SKILL.md").read_text(),
                            (SKILLS / "teardown" / "SKILL.md").read_text())
    print("✓ evolve Step 8 → teardown Step 1: every `$e.<key>` the gate reads is a key the "
          "stamp writes (mode · last_run · candidates · mined_at)")


# --------------------------------------------------------------------------- the meta-check

def breaks(fn, *args):
    try:
        fn(*args)
    except AssertionError:
        return True
    return False


def check_assertions_can_fail():
    """Negative controls for this file itself.

    Bought twice: a check passed while its fix was reverted because the forge re-emitted into
    a dirty /tmp dir and a stale file kept satisfying it; another passed because a file
    rewritten from itself is byte-identical. Both were green for a reason unrelated to the
    thing under test. So each critical assertion above is re-run against a mutated copy of the
    fixture and must fail — against copies under /tmp, never the checked-in files."""
    mut = WORK / "mutants"
    mut.mkdir(parents=True, exist_ok=True)
    signals = json.loads(SIGNALS.read_text())
    clean = json.loads(CLEAN.read_text())
    policy = [e for e in signals["events"] if e.get("kind") == "policy_adopted"]
    assert len(policy) == 1, "fixture drift: ledger-signals.json no longer seeds one policy_adopted"

    # (a) remove a signal from the positive fixture — the by-type assertion must notice.
    dropped = dict(signals, events=[e for e in signals["events"] if e.get("kind") != "policy_adopted"])
    (mut / "signals-no-policy.json").write_text(json.dumps(dropped))
    doc, _, _ = mine(mut / "signals-no-policy.json", "mut-no-policy")
    assert breaks(assert_admissible_profile, doc), \
        "the admissible-signal assertion still passed with policy_adopted deleted from the " \
        "ledger — it is not watching that signal, and this whole file would go green against " \
        "a miner that stopped detecting it"

    # (b) inject an admissible signal into the negative control — silence must break.
    loud = dict(clean, events=clean["events"] + policy)
    (mut / "clean-with-policy.json").write_text(json.dumps(loud))
    doc, _, _ = mine(mut / "clean-with-policy.json", "mut-loud-clean", memory=False)
    assert breaks(assert_clean_admits_nothing, doc), \
        "the negative-control assertion still passed with a policy_adopted injected — then it " \
        "proves nothing about the admission rule biting, which is the one thing it exists for"

    # (c) name the unused gate in an event — the ablation queue must stop listing it.
    exercised = dict(signals, events=signals["events"] + [
        {"ts": "2026-09-01T11:10:00Z", "agent": "worker", "kind": "ticket_gated",
         "payload": {"issue": 1901, "gate": "leak_guard", "result": "pass"}}])
    (mut / "signals-leak-guard-used.json").write_text(json.dumps(exercised))
    doc, _, _ = mine(mut / "signals-leak-guard-used.json", "mut-gate-used")
    assert breaks(assert_unexercised_profile, doc), \
        "the unexercised assertion still passed after an event named leak_guard — a queue " \
        "that lists machinery regardless of use would get pruned on, and prune is destructive"

    # (d) repair one seeded register defect — the per-defect assertion must miss it, which is
    #     what a count-only assertion would not.
    patched = (FX / "lessons-bad.md").read_text().replace(
        "MEMORY.md |  | 2026-09-01", "MEMORY.md | dispatch brief names /tmp | 2026-09-01")
    assert patched != (FX / "lessons-bad.md").read_text(), \
        "fixture drift: lessons-bad.md no longer carries LL-2's empty Check cell"
    (mut / "lessons-patched.md").write_text(patched)
    r = lint(mut / "lessons-patched.md")
    assert r.returncode == 1, "the patched register still has three defects and must still fail"
    assert breaks(assert_bad_register_named, r.returncode, r.stdout + r.stderr), \
        "the lint assertion passed on a register whose empty-Check defect was repaired — it " \
        "is asserting on the exit code, not on the four defects being named individually"

    # (e) repair the phantom heading — the one structural defect that leaves a file looking
    #     clean, so it is the one whose absence is hardest to notice.
    src = (FX / "lessons-structural-bad.md").read_text()
    unwrapped = src.replace(
        "Anecdotes go to\n## Candidates and wait for a second sighting",
        "Anecdotes go to the Candidates table below and wait for a second sighting")
    assert unwrapped != src, \
        "fixture drift: lessons-structural-bad.md no longer wraps prose onto '## Candidates'"
    (mut / "lessons-structural-unwrapped.md").write_text(unwrapped)
    r = lint(mut / "lessons-structural-unwrapped.md")
    assert r.returncode == 1, "three structural defects remain and must still fail"
    assert breaks(assert_structural_register_named, r.returncode, r.stdout + r.stderr), \
        "the structural assertion passed on a register whose phantom heading was repaired — " \
        "it is reading the exit code, not the four defects being named individually"

    # The prose-vocabulary pin. Drop one identity field's backticks and the assertion must
    # notice: the drift it guards against is a rename in the miner that nobody carried into the
    # skill, which looks exactly like this from the prose side.
    run_text = (SKILLS / "run" / "SKILL.md").read_text()
    assert_pairing_vocabulary(run_text)
    assert breaks(assert_pairing_vocabulary, run_text.replace("`issue_key`", "issue_key")), \
        "the pairing-vocabulary assertion passed on prose that stopped naming `issue_key` — " \
        "it is not reading the miner's constants at all"

    print("✓ meta-check: all 6 critical assertions were made to fail against mutated copies "
          "(signal removed · signal injected into the control · gate exercised · row defect "
          "repaired · phantom heading repaired · identity field dropped from the prose)")


def check_new_assertions_can_fail():
    """The same negative-control discipline for the ten fixes this phase bought.

    Kept separate from check_assertions_can_fail only because the mutations are different in
    kind: those bend the fixture's SHAPE (delete a signal, exercise a gate), these bend the
    single input each rule turns on — the null that must not read as a workaround, the
    ordinal that must not read as a tally, the heading whose absence must be said out loud.
    Each mutation is the fix being reverted in the input rather than in the code, which is the
    only way to watch these assertions bite without editing the miner."""
    mut = WORK / "mutants"
    mut.mkdir(parents=True, exist_ok=True)
    signals = json.loads(SIGNALS.read_text())
    pairing = json.loads(PAIRING.read_text())

    def probe(name, body, tag, **kw):
        (mut / name).write_text(json.dumps(body) if not isinstance(body, str) else body)
        return mine(mut / name, tag, **kw)[0]

    # (a) delete the committed `lesson` the note corroborates. The note is written once, so
    #     with nothing left to corroborate it must fall back to an anecdote — if it does not,
    #     this check is reading `repeated` and the corroboration branch is dead again.
    no_lesson = dict(signals, events=[e for e in signals["events"] if e.get("kind") != "lesson"])
    doc = probe("signals-no-lesson.json", no_lesson, "mut-no-lesson", memory=[MEMORY_CORROBORATED])
    assert breaks(assert_corroboration_live, doc), \
        "the corroboration assertion passed with the corroborating ledger event deleted — it " \
        "is asserting that the note exists, not that the branch that admits it ran"

    # (b) turn the compound noun into a real counter shape. Same words, one segment moved:
    #     `third_party` counts nothing and `third_instance` counts three.
    counter = json.loads((WORK / "probes" / "counter-kinds.json").read_text())
    twice = [e for e in counter["events"] if e["kind"] == "third_party_api_timeout"]
    counter["events"] += [dict(twice[0], ts="2026-09-01T09:30:00Z")]
    doc = probe("counter-logged-twice.json", counter, "mut-counter", memory=False)
    assert breaks(assert_counter_kind_bar, doc), \
        "the counter assertion passed with the compound-noun kind logged twice, which the >=2 " \
        "rule admits on its own — the assertion is checking the row exists, not whether it " \
        "cleared the bar"

    # (c) give the null resolution a real value. The pair then forms, which is the proof that
    #     the null — and not the agent, the issue key or the ordering — is what refused it.
    repaired = json.loads(json.dumps(pairing))
    for e in repaired["events"]:
        if e["agent"] == "t-null" and "resolution" in (e.get("payload") or {}):
            e["payload"]["resolution"] = "dispatch the review to the lead when no seat exists"
    doc = probe("pairing-null-repaired.json", repaired, "mut-null", memory=False)
    assert breaks(assert_pairing_profile, doc), \
        "the pairing assertion passed with {'resolution': null} replaced by real text — then " \
        "t-null's refusal has nothing to do with the null and the rule is untested"

    # (e) drop the second identity key from the resolution, leaving `task=T-9` against
    #     `issue=1885`. That is precisely the first-hit-wins miss the fix was bought for.
    split_keys = json.loads(json.dumps(pairing))
    for e in split_keys["events"]:
        if e["kind"] == "ticket_unblocked" and (e.get("payload") or {}).get("task") == "T-9":
            e["payload"].pop("task")
    doc = probe("pairing-split-keys.json", split_keys, "mut-keys", memory=False)
    assert breaks(assert_pairing_profile, doc), \
        "the pairing assertion passed with the resolution's shared identity field removed — " \
        "it is counting rows rather than checking which blocks paired"

    # (f) blank the ticket-less block's reason. Its words are its only identity, so the echo
    #     rule has nothing left to match and the honest record goes back to unpairable.
    mute = json.loads(json.dumps(pairing))
    for e in mute["events"]:
        if e["agent"] == "t-fixture" and e["kind"] == "drift_corrected":
            e["payload"]["resolution"] = "rebuilt the staging seed data and reran the wave"
    doc = probe("pairing-mute.json", mute, "mut-mute", memory=False)
    assert breaks(assert_pairing_profile, doc), \
        "the pairing assertion passed after the answering event stopped sharing any of the " \
        "blocker's words — the no-id path is pairing on adjacency, which is the miss that " \
        "handed a worker's import failure its unrelated PR unblock two hours later"

    # (d) hand the type-warning assertion a well-formed object. No warning is due, so the
    #     assertion must notice; otherwise it passes on any input that writes a document.
    doc, r, _ = mine(SIGNALS, "mut-object-ledger", memory=False)
    assert breaks(assert_nonobject_ledger, doc, r, "a well-formed ledger"), \
        "the non-object assertion passed on an ordinary object ledger — it is asserting that " \
        "a document was written, which every run does"

    # (g) section the flat memory file. The warning is then wrong and must stop.
    flat = mut / "memory-sectioned" / "drain-lead"
    flat.mkdir(parents=True, exist_ok=True)
    (flat / "MEMORY.md").write_text(
        (MEMORY_FLAT / "drain-lead" / "MEMORY.md").read_text().replace(
            "- Dispatching a wave of four", "## cycle-2026-09-01-001\n\n- Dispatching a wave of four"))
    doc, r, _ = mine(SIGNALS, "mut-sectioned", memory=[mut / "memory-sectioned"])
    assert breaks(assert_flat_memory, doc, r.stdout), \
        "the flat-memory assertion passed against a file that HAS cycle headings — it is not " \
        "watching the warning, so a silent skip would read as a pass again"

    # (h) pass the default root a second time as a hand-picked one. It is then mined
    #     unfiltered, which is exactly what the defect did, and the other team's seat appears.
    repo = WORK / "memroots" / "repo"
    doc, _, _ = mine(SIGNALS, "mut-memroots", memory=[repo / ".claude" / "agent-memory"], hub=repo)
    assert breaks(assert_memory_roots, doc, ["drain-worker"], "leaked root"), \
        "the memory-root assertion passed with another team's seat in the mined set — it is " \
        "counting roots rather than naming them, and the leak this fix closed is invisible to it"

    # (i) fail the gate that was waiting on a human. It is then a real failure and must be filed.
    gates = json.loads((WORK / "probes" / "gate-words.json").read_text())
    for e in gates["events"]:
        if (e.get("payload") or {}).get("gate") == "release_signoff":
            e["payload"]["result"] = "failed"
    doc = probe("gate-words-failed.json", gates, "mut-gate-words", memory=False)
    assert breaks(assert_gate_status_words, doc), \
        "the gate-status assertion passed on a release_signoff that genuinely failed — it is " \
        "asserting the gate is never mentioned, which a miner that stopped reading gates gives"

    # (j) re-spell the two incidents as `sev_1`/`sev_2`. The trailing-disambiguator rule then
    #     legitimately collapses them, so the assertion has something to catch.
    norm = json.loads((WORK / "probes" / "normalize.json").read_text())
    for e in norm["events"]:
        if e["kind"] in ("sev1", "sev2"):
            e["kind"] = e["kind"].replace("sev", "sev_")
    doc = probe("normalize-underscored.json", norm, "mut-normalize", memory=False)
    assert breaks(assert_kind_split, doc), \
        "the normalization assertion passed on two kinds that merged into 'sev' — it is not " \
        "watching for the merged noun, which is the whole failure: a claim filed under a word " \
        "no event contains"

    # The two prose contracts, mutated as text — the skills are another agent's to edit, so
    # the assertion is driven against strings rather than against the files on disk.
    evolve_md = (SKILLS / "evolve" / "SKILL.md").read_text()
    teardown_md = (SKILLS / "teardown" / "SKILL.md").read_text()
    assert breaks(assert_handoff_contract, evolve_md,
                  teardown_md.replace("$e.mode", "$e.run_mode")), \
        "the handoff assertion passed with teardown reading a key evolve never writes — that " \
        "gate then reports MISSING on every finished pass and prescribes re-running it forever"
    assert breaks(assert_handoff_contract, evolve_md.replace('"mode": "close|cycle"', '"kind": "x"'),
                  teardown_md), \
        "the handoff assertion passed with the stamp's `mode` renamed — teardown discriminates " \
        "close from cycle on it and would accept a cycle pass as a final one"
    assert breaks(assert_since_documented, [("mutant", "run the miner and read the markdown")]), \
        "the --since assertion passed against prose that never invokes the flag"

    print("✓ meta-check (this phase's fixes): 13 mutations drove every new assertion into "
          "failure (corroborating event deleted · compound-noun kind logged twice · null "
          "resolution repaired · shared identity key dropped · answering event's words "
          "changed · well-formed ledger · memory file sectioned · unfiltered root · gate "
          "really failed · kinds merged to 'sev' · two prose keys renamed · --since dropped)")

def check_fixtures_untouched(before):
    after = fixture_hashes()
    changed = sorted(k for k in before if before[k] != after.get(k))
    assert not changed, \
        f"the run modified checked-in fixtures {changed} — a harness that edits its own " \
        f"inputs proves whatever it just wrote"
    print(f"✓ fixtures untouched: {len(before)} files identical after the run (mutations "
          f"stayed under {WORK})")


def fixture_hashes():
    return {str(p.relative_to(FX)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(FX.rglob("*")) if p.is_file()}


def main():
    assert MINER.exists(), f"miner not found at {MINER}"
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    before = fixture_hashes()

    check_positive_signals()
    check_anecdotes_recorded()
    check_unexercised()
    check_negative_control()
    check_determinism()
    check_register_dedupe()
    check_register_lint()
    check_malformed_inputs()
    check_nonobject_ledgers()
    check_memory_corroboration()
    check_flat_memory()
    check_memory_roots()
    check_counter_kind_bar()
    check_pairing_shapes()
    check_gate_status_words()
    check_kind_normalization()
    check_since_window()
    check_evolve_teardown_handoff()
    check_pairing_vocabulary()
    check_assertions_can_fail()
    check_new_assertions_can_fail()
    check_fixtures_untouched(before)

    print("\nALL EVOLVE CHECKS PASSED")


if __name__ == "__main__":
    main()
