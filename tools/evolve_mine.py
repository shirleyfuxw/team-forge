#!/usr/bin/env python3
"""The evolve phase's deterministic miner — it mines, the model classifies.

Reads a finished cycle's run artifacts (the ledger, design.yaml, manifest.json, the
agents' MEMORY.md files) and emits `candidates-<date>.json` + `candidates-<date>.md`:
every signal the run left behind, each tagged ADMISSIBLE or ANECDOTE against the
evidence bar. No LLM, no network — the `team-forge:evolve` skill reads the .md and
makes the judgment calls the miner deliberately refuses to make.

Why a separate tool at all: the ticket-drainer run that motivated this phase logged 257
events with 78 distinct kinds, ~50 of them appearing exactly once because the lead
invented a noun for something the schema had no slot for — and a human wrote the retro
by hand, two months late, from the same data. Reading a ledger is mechanical; deciding
what a signal MEANS is not. Splitting them keeps the mechanical half reproducible and
auditable, and keeps a model from inventing evidence for a lesson it wants to be true.

Do not import this from forge.py or vice-versa — `forge.py` parses argv and runs an
entire forge at import time. The shared event vocabulary lives in `ledger_vocab.py`
precisely so both can read it without that.

Usage:
  evolve_mine.py <hub-or-repo-path> [--team NAME] [--ledger PATH] [--out DIR]
                 [--since CYCLE_OR_ISO] [--now ISO] [--memory-dir DIR] [--register PATH]
                 [--json]
  evolve_mine.py --lint-register <lessons.md>
"""
import argparse
import itertools
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_vocab import KNOWN_EVENT_KINDS  # noqa: E402

SCHEMA = "team-forge/evolve-candidates/1"
FORGE_VERSION = "0.12.0"

# The default multiple of a soft target that makes a budget line evidence rather than noise.
# 3x is the number the one real overrun cleared by a mile — a team that spent 1010% of its
# soft target, with "six monitor dashboard renders at ~116k each" naming the loss. A team
# raises it in design.yaml's `evolve.budget_overrun_factor` when its own baseline is lumpier.
DEFAULT_BUDGET_OVERRUN_FACTOR = 3

# Payload fields a lead uses to hand-count a repeat. These were maintained BY HAND in a real
# ledger ("occurrence": 2 on a verifier_verdict) — the lead knew it was the second time and
# had nowhere structured to say so. A counter is the lead asserting recurrence directly, so
# it admits a single event where the >=2 rule alone would not.
COUNTER_FIELDS = ("occurrence", "occurrences", "instance", "tally", "count", "nth")
# ...and the same assertion smuggled into the kind name, which is how ~50 nouns got invented.
# Matched against the normalized kind's SEGMENTS (see counter_word), never as substrings:
# "second", "third" and "again" all hide inside ordinary nouns, and a single event of kind
# `third_party_api_timeout` was admitted with the reason "kind names 'third'" — the miner
# claiming the lead counted a recurrence that never happened, which its own docstring forbids.
# Two classes, because a segment match alone does not save the ordinals: "third" is ALSO how
# English builds an ordinary compound, and `third_party` is exactly that. So an ordinal counts
# only where it can be nothing but a tally — last segment (`merge_before_gate_second`) or in
# front of an instance-noun (`third_instance_stale_queue`), the same shape COUNTER_PHRASE
# demands of prose. The repeat words assert a repeat wherever they sit and need no such fence.
COUNTER_ORDINAL_WORDS = ("second", "third", "fourth")
COUNTER_REPEAT_WORDS = ("rediscovered", "again", "repeat", "recurring")
_INSTANCE_NOUNS = ("instance", "instances", "occurrence", "occurrences",
                   "sighting", "sightings", "time", "times")

# The third place a lead hand-counts a repeat: prose. The ticket-drainer ledger states the
# count in the payload text and nowhere else — "Eighth instance of tonight's proxy-substitution
# pattern class" on the fake_green event, "Third instance of this hook's tool-name-as-proxy
# defect class", "merge_before_gate escalated to 3 occurrences". The field-and-kind rules missed
# every one of them, and the single most important lesson of that run (the truthy-string
# fake-green that a bool field invited) sat in the anecdote table because of it. The phrase has
# to be an explicit count immediately in front of an instance-noun, with at most one word
# between: 15 of that ledger's 257 events match and all 15 are real count assertions, while a
# looser scan for the bare word "third" matches prose that is counting nothing.
_ORDINALS = {"second": 2, "two": 2, "third": 3, "three": 3, "fourth": 4, "four": 4,
             "fifth": 5, "five": 5, "sixth": 6, "six": 6, "seventh": 7, "seven": 7,
             "eighth": 8, "eight": 8, "ninth": 9, "nine": 9, "tenth": 10, "ten": 10,
             "eleventh": 11, "eleven": 11, "twelfth": 12, "twelve": 12}
COUNTER_PHRASE = re.compile(
    r"\b(" + "|".join(sorted(_ORDINALS, key=len, reverse=True)) + r"|\d+(?:st|nd|rd|th)?)"
    r"\s+(?:[a-z][a-z-]*\s+)?"
    # "times" is the one noun here that also spells a multiplier. "Three times this cycle,
    # reviewer discovered..." is a count; "three times slower on 114" is a measurement, and
    # admitting it would let the miner manufacture a recurrence out of a benchmark.
    r"(?:instances?|occurrences?|sightings?|"
    r"times(?!\s+(?:faster|slower|larger|smaller|bigger|longer|shorter|higher|lower|more|"
    r"less|worse|better|the|as|over|under|that|than)\b))\b", re.I)

# The payload fields a lead writes its own one-line statement of the finding into. Without
# these the miner's claim sentence is meta-prose about vocabulary ("the lead invented the kind
# 'gate_scope_defect'") while the lesson itself — "every gate that failed this cycle failed the
# same way: the instrument's SCOPE excluded the defect class" — sits unquoted in the excerpt.
# A reader scoring the miner against a hand-written retro called that a miss, and was right to.
HEADLINE_FIELDS = ("label", "finding", "claim", "rule", "statement", "summary", "note")

RESOLUTION_FIELDS = ("resolution", "workaround", "resolved_by", "fix", "unblocked_by")
RESOLVED_WORDS = ("resolved", "unblocked", "cleared")
# Matched as substrings, so every token here has to be a word that cannot hide inside an
# unrelated one. "red" could not: it sits inside "required" and "deferred", and a gate whose
# status was "human sign-off required" — a gate working exactly as designed — came back as a
# gate FAILURE with action add_gate. Dropped rather than wrapped in a word-boundary regex,
# because fail/failed/failure already catch every red gate "red" was there for.
FAIL_WORDS = ("fail", "failed", "failure", "red", "downgraded", "blocked", "defect")
_WORD_RE = re.compile(r"[a-z]+")


def has_fail_word(text):
    """Fail-word test over WORDS, not substrings — `_` and `-` are separators here.

    A bare substring test read "human sign-off required" and "deferred" as red gates, because
    `red` is inside both. Dropping `red` from the vocabulary fixed that and lost the literal
    case: a gate logging `result: "red"` produced no candidate at all, while the run skills
    speak that exact word ("never advance on red"). Splitting into words keeps both."""
    return any(w in FAIL_WORDS for w in _WORD_RE.findall(text.lower()))
# Fields that carry the identity of the thing an agent got blocked on. A blocked->resolved
# pair only counts when both events name the SAME thing: an earlier version matched on agent
# alone and paired a worker's import failure with its unrelated PR unblock two hours later.
ISSUE_FIELDS = ("issue", "issue_number", "issue_key", "ticket", "task", "item", "id", "key", "pr")

SUGGESTION = {
    # signal -> (layer, target template, action). The miner SUGGESTS; only the skill decides.
    "recurrence":          ("L2", "design.yaml#ledger.events", "amend"),
    "recurrence_counter":  ("L2", "design.yaml#gates", "add_gate"),
    "blocked_resolved":    ("L1", ".claude/agent-memory/{team}-lead/MEMORY.md", "amend"),
    "gate_failure":        ("L2", "design.yaml#gates.{name}", "add_gate"),
    "budget_attribution":  ("L2", "design.yaml#{name}", "prune"),
    "policy_adopted":      ("L1", "docs/team-forge/{team}/lessons.md", "amend"),
    "lesson_event":        ("L1", "docs/team-forge/{team}/lessons.md", "amend"),
    "unknown_kind":        ("L1", "docs/team-forge/{team}/lessons.md", "open_item"),
    "memory_note":         ("L1", "docs/team-forge/{team}/lessons.md", "amend"),
}

_STOP = {"that", "this", "with", "from", "into", "when", "have", "been", "were", "will",
         "then", "than", "over", "same", "each", "only", "also", "does", "must", "into",
         "which", "while", "after", "before", "their", "there", "would", "could", "about"}

_OUT = sys.stdout  # rebound to stderr under --json so stdout carries only the document


def say(msg):
    print(msg, file=_OUT)


def warn(msg):
    say(f"⚠ {msg}")


# --------------------------------------------------------------------------- normalization

def normalize_kind(kind):
    """Collapse a lead-invented kind to the claim underneath it.

    `gate_scope_defect` and `gate_scope_defect_2` are one finding logged twice, not two
    findings; so are `drift_corrected` and `drift-corrected`. Counting the raw strings is
    what let a 78-kind ledger look like 78 separate one-off events.

    Exactly one trailing `_<n>` disambiguator comes off, in a single pass. Stripping digits
    to a fixed point collapsed `sev1` and `sev2` into `sev`: two unrelated incidents merged
    into one admissible recurrence, filed under a noun that appears in no event, so a reader
    could not grep back to the evidence. `_corrected`/`_refuted` are no longer stripped at
    all — they assert OPPOSITE things, and `gate_corrected` + `gate_refuted` were being
    counted as a repeat of each other.

    A falsy kind normalizes to "" and never to `"none"` — a truncated ledger with two
    kind-less events was briefly reported as a recurring invented kind called `none`, which
    is the miner fabricating evidence out of its own damage."""
    if not kind or not isinstance(kind, str):
        return ""
    k = re.sub(r"[^a-z0-9]+", "_", str(kind).lower()).strip("_")
    return re.sub(r"_\d+$", "", k).strip("_") or k


def raw_kinds(evs):
    """The kind strings a group was actually logged under, in first-seen order. A claim that
    names only the normalized noun (`gate_scope_defect` for events logged as
    `gate_scope_defect` and `gate_scope_defect_2`) cannot be grepped back to its own
    evidence, so the claim carries both when they differ."""
    seen = []
    for e in evs:
        k = str(e.get("kind") or "").strip()
        if k and k not in seen:
            seen.append(k)
    return seen


def as_logged(evs, norm):
    raws = raw_kinds(evs)
    return f" (logged as {', '.join(raws)})" if raws and raws != [norm] else ""


def tokens(s):
    """Distinctive words, for dedupe and corroboration. Short words are dropped, not
    stoplisted: 'gate', 'leak' and 'wave' carry meaning here and 'the' does not."""
    return {t for t in re.findall(r"[a-z0-9]{4,}", str(s).lower())} - _STOP


def overlap(a, b):
    """Share of the smaller token set that both claims carry. Symmetric-ish on purpose: a
    one-line register row and a three-line candidate describing the same thing should still
    read as the same thing."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def norm_sentence(s):
    """A memory bullet, stripped to its claim: markdown emphasis, backticks and issue
    numbers vary between cycles even when the lesson is verbatim the same."""
    s = re.sub(r"`[^`]*`", " ", str(s))
    s = re.sub(r"[*_#\[\]()]", " ", s)
    s = re.sub(r"#?\d+", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def event_text(ev):
    """Everything an event says, as one `_`-delimited token stream — the corpus the
    unexercised detector searches. Token-delimited so `review` does not match `reviewer`."""
    blob = f"{ev.get('kind','')} {ev.get('agent','')} {json.dumps(ev.get('payload'), sort_keys=True, default=str)}"
    return "_" + re.sub(r"[^a-z0-9]+", "_", blob.lower()).strip("_") + "_"


def mentions(corpus, name):
    n = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    return bool(n) and f"_{n}_" in corpus


def excerpt(payload, limit=200):
    s = json.dumps(payload, sort_keys=True, default=str) if payload else ""
    return s[:limit]


def ref(ev):
    return {"agent": ev.get("agent"), "kind": ev.get("kind"), "ts": ev.get("ts")}


def payload_counter(payload):
    """The count a lead asserted by hand, wherever it put it: a numeric field, or the phrase
    it wrote into its own prose. Returns (n, why) or (None, None). Booleans are refused —
    `{"instance": true}` is a flag, not a tally, and `int(True)` is 1 anyway."""
    if not isinstance(payload, dict):
        return None, None
    for f in COUNTER_FIELDS:
        v = payload.get(f)
        if isinstance(v, bool) or not isinstance(v, int):
            continue
        if v >= 2:
            return v, f"payload.{f}={v}"
    for f, v in sorted(payload.items()):
        if not isinstance(v, str):
            continue
        m = COUNTER_PHRASE.search(v)
        if not m:
            continue
        raw = m.group(1).lower()
        n = _ORDINALS.get(raw) or int(re.sub(r"[^0-9]", "", raw) or 0)
        if n >= 2:
            return n, f"payload.{f} says {m.group(0)!r}"
    return None, None


def counter_word(norm):
    """The repeat the lead smuggled into the kind name — `merge_before_gate_again`, not
    `third_party_api_timeout`. A normalized kind is `_`-delimited, so the word has to BE one
    of its words, and an ordinal has to sit where a compound modifier cannot."""
    parts = norm.split("_")
    for i, w in enumerate(parts):
        if w in COUNTER_REPEAT_WORDS:
            return w
        if w in COUNTER_ORDINAL_WORDS and (i == len(parts) - 1 or parts[i + 1] in _INSTANCE_NOUNS):
            return w
    return None


def headline(payload, limit=160):
    """The payload's own one-line statement of what it found, for the claim sentence. First
    sentence only: these notes run to 2,000 characters and the rest is already in the refs."""
    if not isinstance(payload, dict):
        return ""
    for f in HEADLINE_FIELDS:
        v = payload.get(f)
        if not isinstance(v, str) or len(v.strip()) < 12:
            continue
        line = re.sub(r"\s+", " ", v.strip())
        cut = re.split(r"(?<=[.;])\s", line, maxsplit=1)[0]
        if len(cut) < 12:
            cut = line
        return (cut[: limit - 1] + "…") if len(cut) > limit else cut
    return ""


def with_headline(claim, payload):
    h = headline(payload)
    return f"{claim} — payload says: {h}" if h else claim


def issue_key(payload):
    """The one identity used to NAME a candidate. Pairing uses issue_keys() instead — this
    returns the first hit in ISSUE_FIELDS order, which is a property of which fields happen
    to be present rather than of what the event is about."""
    if not isinstance(payload, dict):
        return None
    for f in ISSUE_FIELDS:
        v = payload.get(f)
        if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v).strip():
            return f"{f}={v}"
    return None


def issue_keys(payload):
    """EVERY identity the payload names, so two events can be compared by intersection. A
    block carrying {"task": "T-9"} and its resolution carrying {"issue": 1885, "task": "T-9"}
    produced the single keys 'task=T-9' and 'issue=1885' and never paired — the resolution
    was written by an agent that had the ticket number to hand and the block was not."""
    if not isinstance(payload, dict):
        return set()
    return {f"{f}={payload[f]}" for f in ISSUE_FIELDS
            if isinstance(payload.get(f), (str, int))
            and not isinstance(payload.get(f), bool) and str(payload[f]).strip()}


# --------------------------------------------------------------------------- input loading

def load_json(path, what):
    try:
        d = json.loads(Path(path).read_text())
    except FileNotFoundError:
        warn(f"{what} not found at {path} — that input contributes nothing")
        return {}
    except Exception as e:  # a half-written ledger from a killed cycle must not lose the rest
        warn(f"{what} at {path} is unreadable ({e.__class__.__name__}: {e}) — skipped")
        return {}
    if not isinstance(d, dict):
        # Valid JSON that is not an object parses cleanly and then explodes on the first
        # `.get` — ledger.get("events"), budget, manifest.get("forge_version"). A ledger of
        # `[{"kind": "cycle_started"}]` exited 1 with an uncaught AttributeError and wrote NO
        # document, so the cycle lost its other inputs too. Mirrors load_yaml's isinstance
        # guard: this tool runs unattended and must never abort on a type.
        warn(f"{what} at {path} is a JSON {type(d).__name__}, not an object — skipped")
        return {}
    return d


def load_yaml(path, what):
    try:
        import yaml
    except ImportError:
        warn("pyyaml not installed — design.yaml inputs skipped (pip3 install pyyaml)")
        return {}
    try:
        d = yaml.safe_load(Path(path).read_text())
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        warn(f"{what} not found at {path} — team-declared kinds, gates and skill gaps unknown")
    except Exception as e:
        warn(f"{what} at {path} is unreadable ({e.__class__.__name__}: {e}) — skipped")
    return {}


def resolve_hub(raw, team_arg):
    """Accept either the team hub or the repo root, because both are what a caller has in
    hand: the skill runs from the repo root and knows its team, a human debugging a mined
    file is already cd'd into the hub. Returns (hub, repo_root, team)."""
    p = Path(raw).resolve()
    if team_arg:
        cand = p / ".claude" / "team-forge" / team_arg
        if cand.is_dir():
            return cand, p, team_arg
        if p.name == team_arg:
            return p, repo_root_of(p), team_arg
        return p, repo_root_of(p), team_arg
    tf = p / ".claude" / "team-forge"
    if tf.is_dir():
        hubs = sorted(d for d in tf.iterdir() if d.is_dir())
        if len(hubs) == 1:
            return hubs[0], p, hubs[0].name
        if not hubs:
            sys.exit(f"✗ no forged team under {tf} — pass --team, or point at the hub directly")
        sys.exit(f"✗ {len(hubs)} teams under {tf} ({', '.join(h.name for h in hubs)}) — pass --team")
    team = p.name
    m = load_json(p / "manifest.json", "manifest.json") if (p / "manifest.json").exists() else {}
    return p, repo_root_of(p), m.get("team") or team


def repo_root_of(hub):
    """`<repo>/.claude/team-forge/<team>` -> `<repo>`. A hub that does not sit in that
    layout (a fixture, an archived copy) is its own root; the alternative is walking up two
    arbitrary levels and mining a neighbouring project's `.claude/`."""
    parts = hub.resolve().parts
    if len(parts) >= 3 and parts[-2] == "team-forge" and parts[-3] == ".claude":
        return Path(*parts[:-3])
    return hub.resolve()


# --------------------------------------------------------------------------- the six signals

def mine_recurrence(events, known, team):
    """Signals 1 and 7 — the same claim logged twice, or hand-counted once.

    Only INVENTED kinds count toward the >=2 rule. A known kind recurring is the workflow
    working: `ticket_triaged` fired 53 times in the run that motivated this phase and means
    nothing. An invented kind firing twice means the vocabulary was missing a word and the
    lead needed it more than once."""
    out = []
    groups = {}
    for ev in events:
        norm = normalize_kind(ev.get("kind"))
        if not norm or norm in known:
            continue
        groups.setdefault(norm, []).append(ev)

    for norm in sorted(groups):
        evs = groups[norm]
        if len(evs) >= 2:
            out.append(candidate(
                signal="recurrence",
                claim=with_headline(
                    f"the lead invented the event kind '{norm}'{as_logged(evs, norm)} and needed "
                    f"it {len(evs)} times — the ledger vocabulary has no slot for what it names",
                    evs[0].get("payload")),
                count=len(evs), refs=[ref(e) for e in evs[:5]],
                excerpt_of=evs[0].get("payload"),
                admissible=True, reason=f"recurrence>={len(evs)}",
                team=team, name=norm))

    # A counter admits a single event, and applies to KNOWN kinds too: the real one rode on a
    # `verifier_verdict` payload, where the kind was fine and the finding was the repeat.
    for ev in events:
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        norm = normalize_kind(ev.get("kind"))
        if norm in {c["_name"] for c in out}:
            continue  # already admitted by count; a counter on top adds nothing
        n, why = payload_counter(pl)
        word = counter_word(norm)
        if n is None and word is None:
            continue
        if n is None:
            why = f"kind names '{word}'"
        out.append(candidate(
            signal="recurrence",
            claim=with_headline(
                f"'{norm}'{as_logged([ev], norm)} carries a hand-maintained repeat counter "
                f"({why}) — the lead counted the recurrence itself because nothing else was "
                f"counting it", pl),
            count=n or 2, refs=[ref(ev)], excerpt_of=pl,
            admissible=True, reason=f"recurrence counter ({why})",
            team=team, name=norm, suggest_as="recurrence_counter"))
    return out


def blocker_echo(blocker, later):
    """Does a later event talk about the same trouble as a ticket-less block?

    The bar is deliberately steep, because this is the pairing rule with no id behind it:
    half of the blocker's distinctive words have to reappear in the later event, and at
    least two of them. One shared word pairs a worker's import failure with its unrelated
    PR unblock two hours later, which is the miss this whole signal was tightened for; a
    blocker that stated no reason at all ('unstated') carries one token and can never clear
    it, so it stays an anecdote rather than pairing with whatever came next."""
    text = json.dumps(later.get("payload"), sort_keys=True, default=str) + " " + \
        str(later.get("kind") or "")
    shared = tokens(blocker) & tokens(text)
    return len(shared) >= 2 and overlap(blocker, text) >= 0.5


def mine_blocked_resolved(events, team):
    """Signal 2 — an `agent_blocked` that a later event answers. The workaround is already
    written down and already worked; it is a lesson with its proof attached. Unresolved
    blocks stay anecdotes: nobody has shown the fix works."""
    out = []
    for i, ev in enumerate(events):
        if normalize_kind(ev.get("kind")) != "agent_blocked":
            continue
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        key, keys, agent = issue_key(pl), issue_keys(pl), ev.get("agent")
        blocker = pl.get("reason") or pl.get("blocker") or pl.get("note") or key or "unstated"
        match = None
        for later in events[i + 1:]:
            lpl = later.get("payload") if isinstance(later.get("payload"), dict) else {}
            # Identity by intersection, not by each side's first hit — see issue_keys().
            # A shared ticket id is sufficient on its own, and deliberately does NOT also
            # require an agent match: a worker blocks and the LEAD logs the unblock against
            # the same ticket without naming the worker, which is the routine shape. The id
            # is a stronger handle than who typed the event, and gating it on the agent too
            # dropped exactly the lead-logged workarounds this signal exists to keep.
            if keys:
                if not (keys & issue_keys(lpl)):
                    continue
            else:
                # No ticket at all (a complete, honest record: "pre-commit secret hook flags
                # generated fixtures"). Now the agent and the blocker's own words are the only
                # identity there is, so both are required — the pair of them is what stops an
                # unrelated later event from answering a block it has nothing to do with.
                if later.get("agent") != agent and not (agent and mentions(event_text(later), agent)):
                    continue
                if not blocker_echo(blocker, later):
                    continue
            status = str(lpl.get("status") or "").lower()
            resolved = any(w in status for w in RESOLVED_WORDS) \
                or any(w in normalize_kind(later.get("kind")) for w in RESOLVED_WORDS) \
                or any(str(lpl.get(f) or "").strip() for f in RESOLUTION_FIELDS)
            if resolved:
                match = later
                break
        if match:
            mpl = match.get("payload") if isinstance(match.get("payload"), dict) else {}
            # `.get(f, "")` returns None, not the default, when the key is present with a JSON
            # null — and str(None) is the truthy "None". A payload of {"resolution": null}
            # both satisfied the pairing and rendered as "resolved in-run by: None". Null
            # placeholders are routine in this ledger shape (register_id: null).
            fix = next((str(mpl[f]) for f in RESOLUTION_FIELDS if str(mpl.get(f) or "").strip()),
                       "resolved, workaround unstated")
            out.append(candidate(
                signal="blocked_resolved",
                claim=f"{agent} blocked on {blocker} — resolved in-run by: {fix}",
                count=2, refs=[ref(ev), ref(match)], excerpt_of=mpl,
                admissible=True, reason="blocked->resolved with the workaround recorded",
                team=team, name=str(key or agent)))
        else:
            out.append(candidate(
                signal="blocked_resolved",
                claim=f"{agent} blocked on {blocker} — no matching resolution in this window",
                count=1, refs=[ref(ev)], excerpt_of=pl,
                admissible=False, reason="no later event resolves it — the workaround, if there was one, went unrecorded",
                team=team, name=str(key or agent)))
    return out


def mine_gate_failures(events, team):
    """Signal 3 — a gate that failed AND says why. Without a root cause a red gate is just
    a red gate; three runs shipped unsatisfiable gates in design.yaml and the ledger showed
    only that they never went green."""
    out = []
    for ev in events:
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        norm = normalize_kind(ev.get("kind"))
        if "gate" not in norm and "gate" not in {k.lower() for k in pl}:
            continue
        verdicts = " ".join(str(pl.get(f, "")).lower() for f in ("result", "status", "verdict", "outcome"))
        if not (has_fail_word(norm) or has_fail_word(verdicts)):
            continue
        gate = pl.get("gate") or pl.get("gate_name") or norm
        cause = str(pl.get("root_cause") or pl.get("reason") or "").strip()
        if cause:
            out.append(candidate(
                signal="gate_failure",
                claim=f"gate '{gate}' failed — root cause: {cause}",
                count=1, refs=[ref(ev)], excerpt_of=pl,
                admissible=True, reason="gate failure carries a root cause",
                team=team, name=str(gate)))
        else:
            out.append(candidate(
                signal="gate_failure",
                claim=f"gate '{gate}' failed with no root cause recorded",
                count=1, refs=[ref(ev)], excerpt_of=pl,
                admissible=False, reason="gate failure without a root_cause/reason is not yet a lesson",
                team=team, name=str(gate)))
    return out


def mine_budget(ledger, factor, team):
    """Signal 4 — a line that ate the run. Handles both shapes seen in the wild: a real
    ledger carried `budget.per_task`, the workflow shape carries `budget.by_unit`, and both
    sit alongside one `soft_target`. Per-line `soft_target` wins when present."""
    out = []
    budget = ledger.get("budget")
    if not isinstance(budget, dict) or not budget:
        return out
    default_target = budget.get("soft_target")
    if not isinstance(default_target, (int, float)):
        default_target = None
    seen_any = False
    # The whole-run line first. `budget.spent` against `budget.soft_target` is the number a
    # human actually acts on — the barra-backbone run spent 1010% of its target and every
    # individual per_task line was under 5x, so a per-line-only miner reported a 4.5x blip and
    # never said the run as a whole had blown its budget by an order of magnitude. The note
    # rides along in the excerpt because that is where the attribution lives ("six monitor
    # dashboard renders at ~116k each"), and naming the seat is what got a seat cut.
    total, _own = _spend(budget)
    if total is not None and default_target and total > factor * default_target:
        seen_any = True
        note = budget.get("note")
        note = f" — budget note: {md_cell(note)[:280]}" if isinstance(note, str) else ""
        out.append(candidate(
            signal="budget_attribution",
            claim=f"the run as a whole spent {total:,.0f} against a soft target of "
                  f"{default_target:,.0f} ({total / default_target:.1f}x, over the "
                  f"{factor}x bar){note}",
            count=1, refs=[{"agent": None, "kind": "budget.spent", "ts": None}],
            excerpt_of={"spent": total, "soft_target": default_target,
                        "note": budget.get("note")},
            admissible=True, reason=f"whole-run spend {total / default_target:.1f}x > {factor}x soft target",
            team=team, name="whole-run"))
    for map_name in ("per_task", "by_unit"):
        m = budget.get(map_name)
        if not isinstance(m, dict):
            continue
        for label in sorted(k for k in m if k != "soft_target"):
            spend, own_target = _spend(m[label])
            target = own_target if own_target else default_target
            if spend is None or not target:
                continue
            seen_any = True
            if spend > factor * target:
                out.append(candidate(
                    signal="budget_attribution",
                    claim=f"budget line '{label}' spent {spend:,.0f} against a soft target of "
                          f"{target:,.0f} ({spend / target:.1f}x, over the {factor}x bar)",
                    count=1, refs=[{"agent": None, "kind": f"budget.{map_name}", "ts": None}],
                    excerpt_of={label: m[label], "soft_target": target},
                    admissible=True, reason=f"spend {spend / target:.1f}x > {factor}x soft target",
                    # Budget labels are prose ("six monitor dashboard renders at ~116k each"),
                    # and a `design.yaml#...` target with spaces and parens in it is not a
                    # pointer to anything. Slugged for the target; the claim keeps the prose.
                    team=team, name=re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")))
    if not seen_any and default_target is None:
        warn("budget present but carries no soft_target — the budget signal is skipped, not failed")
    return out


def _spend(v):
    if isinstance(v, bool):
        return None, None
    if isinstance(v, (int, float)):
        return float(v), None
    if isinstance(v, dict):
        for k in ("spent", "spend", "tokens", "total"):
            if isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool):
                t = v.get("soft_target")
                return float(v[k]), float(t) if isinstance(t, (int, float)) else None
    return None, None


def mine_policies(events, team):
    """Signal 5 — admissible by definition. A `policy_adopted` is a rule the lead already
    applied for the rest of the run and that lives in no file: the next cycle starts without
    it. Grouped by policy identity so re-declaring one mid-run is still one lesson."""
    out, groups = [], {}
    for ev in events:
        if normalize_kind(ev.get("kind")) != "policy_adopted":
            continue
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        ident = str(pl.get("policy") or pl.get("name") or pl.get("rule") or ev.get("ts") or "policy")
        groups.setdefault(ident, []).append(ev)
    for ident in sorted(groups):
        evs = groups[ident]
        pl = evs[0].get("payload") or {}
        rule = str(pl.get("rule") or pl.get("statement") or ident).strip()
        out.append(candidate(
            signal="policy_adopted",
            claim=f"policy '{ident}' was adopted mid-run and lives in no file: {rule}",
            count=len(evs), refs=[ref(e) for e in evs[:5]], excerpt_of=pl,
            admissible=True, reason="policy_adopted is admissible by definition",
            team=team, name=ident))
    return out


def mine_lesson_events(events, team):
    """Signal 6 — a `lesson` the lead already committed to. `status: candidate` is the lead
    saying "I am not sure yet", and the miner honours that: it stays an anecdote."""
    out, groups = [], {}
    for ev in events:
        if normalize_kind(ev.get("kind")) != "lesson":
            continue
        pl = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        groups.setdefault(str(pl.get("claim") or ev.get("ts") or "lesson"), []).append(ev)
    for claim in sorted(groups):
        evs = groups[claim]
        pl = evs[0].get("payload") or {}
        status = str(pl.get("status") or "candidate").lower()
        ok = status != "candidate"
        c = candidate(
            signal="lesson_event",
            claim=claim,
            count=len(evs), refs=[ref(e) for e in evs[:5]], excerpt_of=pl,
            admissible=ok,
            reason=f"lesson event with status={status!r}" if ok
                   else "lesson event still status=candidate — the lead has not committed to it",
            team=team, name=claim[:40])
        # The lead's own routing beats the miner's heuristic when it stated one.
        if pl.get("layer"):
            c["suggested_layer"] = str(pl["layer"])
        if pl.get("target"):
            c["suggested_target"] = str(pl["target"])
        if pl.get("action"):
            c["suggested_action"] = str(pl["action"])
        out.append(c)
    return out


def mine_singletons(events, known, team):
    """The anecdote floor. A kind invented once and never reused is a design defect worth
    RECORDING and not worth ACTING on — acting on all ~50 of them is how a register becomes
    a wall nobody reads."""
    out, groups = [], {}
    for ev in events:
        norm = normalize_kind(ev.get("kind"))
        if not norm or norm in known:
            continue
        groups.setdefault(norm, []).append(ev)
    for norm in sorted(groups):
        evs = groups[norm]
        if len(evs) != 1:
            continue
        pl = evs[0].get("payload") if isinstance(evs[0].get("payload"), dict) else {}
        if payload_counter(pl)[0] is not None or counter_word(norm) is not None:
            continue  # already admitted by the counter rule
        out.append(candidate(
            signal="unknown_kind",
            claim=with_headline(
                f"one-off event kind '{norm}'{as_logged(evs, norm)} — a noun invented for "
                f"something the schema had no slot for, used once", pl),
            count=1, refs=[ref(evs[0])], excerpt_of=pl,
            admissible=False, reason="single invented kind, no counter — anecdote",
            team=team, name=norm))
    return out


# The section label a flat memory file's notes are filed under. Native agent memory is
# self-curated and nothing instructs an agent to write '## <cycle-id>' headings, so a flat
# bullet list has to surface as SOMETHING — under a fixed label, because two runs of the
# miner at the same --now have to be byte-identical.
UNSECTIONED = "(no cycle headings)"


def memory_notes(text, default_section):
    """Bullets, grouped by the normalized sentence, with the cycle sections each appeared in.
    `default_section` is None for the sectioned pass (bullets before the first '## ' heading
    are prologue and are skipped) and UNSECTIONED for the fallback pass."""
    cycles, notes = default_section, {}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            cycles = s[3:].strip()
            continue
        if s.startswith("#") or s.startswith("|") or not cycles:
            continue
        m = re.match(r"^[-*]\s+(.*\S)\s*$", s)
        if not m or len(m.group(1)) < 25:
            continue
        note = m.group(1)
        key = norm_sentence(note)
        if not key:
            continue
        rec = notes.setdefault(key, {"text": note, "cycles": [], "n": 0})
        rec["n"] += 1
        if cycles not in rec["cycles"]:
            rec["cycles"].append(cycles)
    return notes


def mine_memory(memory_files, ledger_candidates, team):
    """Memory notes. Native per-agent memory is written every cycle and harvested never — a
    note recording a hook false positive took two months to become a code fix. But one
    agent's one-time observation is not evidence, so a note is admitted only when the SAME
    normalized sentence survives into a second cycle section, or when it corroborates
    something the ledger independently shows."""
    out = []
    for path in memory_files:
        try:
            text = Path(path).read_text()
        except Exception as e:
            warn(f"memory file {path} unreadable ({e.__class__.__name__}) — skipped")
            continue
        notes = memory_notes(text, None)
        if not notes:
            # A file with no '## ' headings mined to zero notes in silence while
            # source.memory_dirs still listed it — which reads as "nothing to learn" rather
            # than "not parsed". Nothing instructs an agent to shape MEMORY.md that way, so
            # the file is not at fault: say what was looked for, and fall back to one section
            # so the bullets at least surface as anecdotes.
            notes = memory_notes(text, UNSECTIONED)
            if notes:
                warn(f"{path} has no '## <cycle-id>' headings — the cross-cycle repeat rule "
                     f"needs them, so its {len(notes)} note(s) are mined as one section and "
                     f"can only be admitted by corroborating the ledger")
            else:
                warn(f"{path} yielded no notes — looked for '- '/'* ' bullets of 25+ "
                     f"characters, under '## <cycle-id>' headings and then anywhere in the "
                     f"file, and found none")
        agent = Path(path).parent.name
        for key in sorted(notes):
            rec = notes[key]
            repeated = len(rec["cycles"]) >= 2
            # Match against the candidate's EVIDENCE as well as the miner's claim sentence.
            # The claim is the miner's own words ("the lead invented the kind ..."), so three
            # verifier memory notes recording the branch-safety hook blocking its own writes
            # failed to corroborate the branch-safety ledger events they were describing —
            # the shared vocabulary was all in the payload, which the claim never quoted.
            # The MATCHED CANDIDATE, not its id: ids are assigned after the sort, which runs
            # long after this, so keying on c["id"] compared None against None and returned
            # the first candidate on a MATCH and on a MISS alike. `admissible` then collapsed
            # to bool(repeated) and this whole branch was dead — a note stating the exact
            # claim three ledger events independently prove was filed "uncorroborated".
            # main() stitches the id in once the sort has assigned one.
            # Only an ADMISSIBLE candidate corroborates. Scanning every candidate let a note
            # that merely echoed a REFUSED row back into evidence: one sighting of
            # `third_party_api_timeout` is an anecdote, and the same lead writing it down in
            # memory is that one sighting recorded twice, not a second sighting. Without this
            # clause a note re-admitted the exact rows the counter-word fix exists to refuse.
            corroborates = next((c for c in ledger_candidates
                                 if c["admissible"]
                                 and (overlap(c["claim"], rec["text"]) >= 0.6
                                      or overlap(c["evidence"]["excerpt"], rec["text"]) >= 0.6)), None)
            if repeated:
                reason = f"same note in {len(rec['cycles'])} cycle sections ({', '.join(rec['cycles'])})"
            elif corroborates:
                reason = "corroborates a ledger candidate"
            else:
                reason = "single note in one cycle section, uncorroborated — anecdote"
            note_c = candidate(
                signal="memory_note",
                claim=f"{agent} memory: {rec['text']}",
                count=len(rec["cycles"]),
                refs=[{"agent": agent, "kind": "memory_note", "ts": c} for c in rec["cycles"][:5]],
                excerpt_of={"note": rec["text"]},
                admissible=bool(repeated or corroborates), reason=reason,
                team=team, name=agent)
            if corroborates is not None and not repeated:
                note_c["_corroborates"] = corroborates
            out.append(note_c)
    return out


def candidate(signal, claim, count, refs, excerpt_of, admissible, reason, team, name,
              suggest_as=None):
    layer, target, action = SUGGESTION[suggest_as or signal]
    return {
        "id": None,  # assigned after the stable sort
        "signal": signal,
        "claim": claim,
        "evidence": {"count": count, "refs": refs, "excerpt": excerpt(excerpt_of)},
        "admissible": bool(admissible),
        "admission_reason": reason,
        "suggested_layer": layer,
        "suggested_target": target.format(team=team, name=name),
        "suggested_action": action,
        "related_lessons": [],
        "status": "new",
        "_name": name,
    }


# --------------------------------------------------------------------------- unexercised

def mine_unexercised(design, manifest, events, repo_root, team):
    """The ablation queue. GOAL.md's doctrine is to prune as well as accrete: a gate no
    event ever names, an agent nobody dispatched and a skill gap nobody promoted are the
    three shapes of machinery that a run carried and never used."""
    out = []
    per_event = [event_text(e) for e in events]
    corpus = "".join(per_event)
    agents_seen = {re.sub(r"[^a-z0-9]+", "_", str(e.get("agent", "")).lower()).strip("_")
                   for e in events}
    # A seat that wrote nothing is exonerated only by being genuinely present in the run's
    # traffic, not by one passing mention. Single-writer ledgers attribute every event to the
    # tracker, so authorship alone would condemn four working seats — but any-mention is the
    # opposite error: the monitor seat a human cut after ~4 renders for zero human views was
    # named in 2 of 257 events, and the miner's `_monitor_ in corpus` test called it exercised
    # and dropped it from the ablation queue. Below ~2% of the window a seat is a mention, not
    # a participant; the count goes into the reason so the reader checks rather than trusts.
    floor = max(1, -(-len(events) * 2 // 100))

    for gname in sorted((design.get("gates") or {}) if isinstance(design.get("gates"), dict) else {}):
        if not mentions(corpus, gname):
            out.append({"kind": "gate", "name": gname,
                        "reason": "declared in design.yaml; no event in this window names it — "
                                  "either it never ran or it runs unlogged"})

    forged_kinds = {"workflow_profile", "agent_md", "monitor_agent", "lead_agent"}
    for entry in (manifest.get("generated_files") or []):
        if entry.get("kind") not in forged_kinds:
            continue
        stem = Path(str(entry.get("path", ""))).stem
        short = stem[len(team) + 1:] if stem.startswith(f"{team}-") else stem
        norm_stem = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        if norm_stem in agents_seen or short in agents_seen:
            continue
        named = sum(1 for t in per_event if mentions(t, stem) or mentions(t, short))
        if named > floor:
            continue
        out.append({"kind": "agent", "name": stem,
                    "reason": f"forged as {entry['kind']}; zero events attributed to it and "
                              f"{named} of {len(events)} events name it — a seat the run paid "
                              f"for and barely filled" if named else
                              f"forged as {entry['kind']}; zero events attributed to it or "
                              f"naming it — a seat the run paid for and never filled"})

    for gap in (design.get("skill_gaps") or []):
        name = (gap or {}).get("name")
        if not name:
            continue
        if (repo_root / ".claude" / "skills" / str(name) / "SKILL.md").exists():
            continue
        if mentions(corpus, name):
            continue
        out.append({"kind": "skill_gap", "name": str(name),
                    "reason": "declared in design.yaml skill_gaps, never promoted to "
                              ".claude/skills/, and no event references it"})
    return sorted(out, key=lambda u: (u["kind"], u["name"]))


# --------------------------------------------------------------------------- the register

_TABLES = {"active": "## active", "superseded": "## superseded",
           "candidates": "## candidates", "unexercised": "## unexercised"}


def parse_register(path):
    """Read a lessons.md into {section: [{header: cell}]} plus the raw id list. Tolerant on
    purpose — the linter reports defects, and a parser that refuses to parse a defective
    file cannot report them."""
    out = {k: [] for k in _TABLES}
    headers = {}          # section -> the header cells it actually declared
    seen_headings = []    # (section, literal heading) for every line that switched sections
    banner = False
    try:
        text = Path(path).read_text()
    except Exception:
        return out, [], False, {"_headers": headers, "_headings": seen_headings}
    section, header = None, None
    ids = []
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if re.search(r"verified against team-forge\s+\**\d+\.\d+\.\d+", low):
            banner = True
        if s.startswith("##"):
            section, header = None, None
            for key, prefix in _TABLES.items():
                if low.startswith(prefix):
                    section = key
                    seen_headings.append((key, s))
            continue
        if not section or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            headers.setdefault(section, header)
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        row = dict(zip(header, cells))
        row["_raw"] = s
        out[section].append(row)
        first = cells[0] if cells else ""
        if re.match(r"^\*{0,2}(LL|C)-\d+", first, re.I):
            ids.append(re.sub(r"[*`]", "", first).strip())
    return out, ids, banner, {"_headers": headers, "_headings": seen_headings}


def cell(row, *names):
    for n in names:
        for k, v in row.items():
            if k != "_raw" and n in k:
                return v.strip()
    return ""


# The column each table must carry, keyed by the cell(row, ...) substring that finds it.
# A register missing a whole section, or a section that quietly dropped a column, parses
# fine and lints clean under a row-only linter — every rule below has nothing to iterate
# over, so an empty table and an absent one look identical. references/register-format.md
# has always documented "the four sections exist with their expected columns"; until this
# rule existed that sentence described nothing.
_REQUIRED_SECTIONS = {
    "active":      ("## Active", ("#", "lesson", "evidence", "applied to", "check", "since")),
    "superseded":  ("## Superseded / falsified", ("#", "lesson", "died at", "replaced by")),
    "candidates":  ("## Candidates (evidence pending)", ("c-id", "claim", "seen", "first/last")),
    "unexercised": ("## Unexercised (ablation queue)", ("what", "since", "runs without a trace",
                                                        "decision")),
}


def lint_register(path):
    """Seven rules, each bought by a way a register stops being a register: a missing
    section or a dropped column makes every row rule vacuous (an empty table and an absent
    one lint identically); duplicate ids make LL-4 ambiguous forever (ids are append-only
    and cited from code comments); an Active row without Evidence, Applied-to or Check is
    the exact thing the admission bar exists to prevent, smuggled in as a table row; two
    Active rows making the same claim is already two registers, and they start disagreeing
    at the first supersede; a Superseded row with no 'Died at' loses WHY the belief died, so
    the next reader re-derives it from the same plausible reasoning; and a missing banner is
    the failure the model register was built around — a wrong belief indistinguishable from
    a checked one.

    What it deliberately does NOT check, because it is handed one file path and nothing
    else: that ids were not renumbered since the previous commit (needs git), and that every
    register_id cited by a `lesson` event resolves to a row (needs the ledger). Both are the
    evolve skill's job at Step 8, where both inputs are in hand."""
    p = Path(path)
    if not p.exists():
        say(f"✗ register not found: {path}")
        return 1
    tables, ids, banner, meta = parse_register(p)
    headers, headings = meta["_headers"], meta["_headings"]
    defects = []

    # A phantom heading: prose that line-wrapped onto a `## <section>` line. The parser
    # switches sections on ANY line starting `##`, so a wrapped sentence silently reassigns
    # every table that follows it — and the file still lints clean, because the rules below
    # then run over the wrong rows. The forge shipped exactly this: templates/lessons.md.j2
    # wrapped "Anecdotes go to ## Candidates and wait for a second sighting" onto its own
    # line, giving every forged register a second, bogus Candidates heading mid-paragraph.
    for key, literal in headings:
        title = _REQUIRED_SECTIONS[key][0]
        if literal.strip().lower() != title.lower():
            defects.append(f"heading {literal.strip()!r} starts like the {key} section but is not "
                           f"'{title}' — a wrapped prose line beginning '##' reads as a section "
                           f"switch, and the rows after it are then linted as the wrong table")

    for key, (title, required) in _REQUIRED_SECTIONS.items():
        if key not in headers:
            defects.append(f"missing section '{title}' — a register with no {key} table cannot "
                           f"be linted for it, and an absent table reads exactly like an empty one")
            continue
        have = headers[key]
        missing = [c for c in required if not any(c in h for h in have)]
        if missing:
            defects.append(f"section '{title}': column(s) {missing} missing (header is {have}) — "
                           f"a dropped column makes every row rule that reads it vacuous")

    seen = {}
    for i in ids:
        seen[i] = seen.get(i, 0) + 1
    for i in sorted(k for k, n in seen.items() if n > 1):
        defects.append(f"duplicate id {i} (appears {seen[i]}x) — ids are append-only and never reused")
    for row in tables["active"]:
        rid = cell(row, "#") or row["_raw"][:40]
        if not cell(row, "evidence"):
            defects.append(f"Active row {rid}: Evidence cell empty — an unevidenced row is a "
                           f"Candidate, not a lesson")
        if not cell(row, "applied to"):
            defects.append(f"Active row {rid}: 'Applied to' cell empty — a lesson that names no "
                           f"layer:path was never applied to anything")
        if not cell(row, "check"):
            defects.append(f"Active row {rid}: Check cell empty — name the check that proves it, "
                           f"or the lesson is unverifiable")
    for a, b in itertools.combinations(tables["active"], 2):
        ca, cb = cell(a, "lesson"), cell(b, "lesson")
        if ca and cb and overlap(ca, cb) >= 0.85:
            defects.append(f"Active rows {cell(a, '#') or '?'} and {cell(b, '#') or '?'} make the "
                           f"same claim — one lesson carried twice is two registers, and they "
                           f"start disagreeing at the first supersede")
    for row in tables["superseded"]:
        rid = cell(row, "#") or row["_raw"][:40]
        if not cell(row, "died at"):
            defects.append(f"Superseded row {rid}: 'Died at' empty — a falsified claim without "
                           f"what killed it teaches nothing")
    if not banner:
        defects.append("no version banner — a register with no 'Verified against team-forge <x.y.z>' "
                       "line cannot tell a checked belief from a stale one")
    for d in defects:
        say(f"✗ {d}")
    if defects:
        return 1
    say(f"✓ {p.name}: register valid — {len(tables['active'])} active, "
        f"{len(tables['superseded'])} superseded, {len(tables['candidates'])} candidates, banner present")
    return 0


def next_ids(tables, ids):
    def top(prefix):
        ns = [int(m.group(1)) for i in ids
              if (m := re.match(rf"^{prefix}-(\d+)$", re.sub(r"[*`]", "", i.strip()), re.I))]
        return max(ns) if ns else 0
    return top("C") + 1, top("LL") + 1


# --------------------------------------------------------------------------- rendering

def render_md(doc, ledger_path):
    s = doc["source"]
    adm = [c for c in doc["candidates"] if c["admissible"]]
    anec = [c for c in doc["candidates"] if not c["admissible"]]
    L = [f"# {doc['team']} — evolve candidates · {doc['mined_at'][:10]}", "",
         f"> Mined by `tools/evolve_mine.py` from `{ledger_path}` — {s['events']} events"
         f"{', cycles: ' + ', '.join(s['cycles']) if s['cycles'] else ''} · "
         f"team-forge **{doc['forge_version']}** · mined_at {doc['mined_at']}",
         "> Admissible = evidence met the bar. Anecdotes are RECORDED, never applied — that is "
         "the whole point of the split.", ""]

    L += [f"## Admissible ({len(adm)})", ""]
    if not adm:
        L += ["_Nothing cleared the evidence bar in this window._", ""]
    for c in adm:
        L += [f"### {c['id']} · {c['signal']} — {c['claim']}",
              f"- **Admitted because**: {c['admission_reason']} (count {c['evidence']['count']})",
              f"- **Refs**: " + ("; ".join(
                  f"`{r.get('ts') or '—'}` {r.get('kind')}" + (f" ({r['agent']})" if r.get("agent") else "")
                  for r in c["evidence"]["refs"]) or "—"),
              f"- **Suggests**: {c['suggested_layer']} · `{c['suggested_target']}` · "
              f"{c['suggested_action']}"]
        if c["related_lessons"]:
            L += [f"- **Related**: {', '.join(c['related_lessons'])} (status: {c['status']})"]
        if c["evidence"]["excerpt"]:
            L += [f"- **Excerpt**: `{c['evidence']['excerpt']}`"]
        L += [""]

    L += [f"## Candidates / anecdotes ({len(anec)}) — recorded, never applied", ""]
    if anec:
        L += ["| id | signal | claim | seen | why it is not evidence |",
              "|---|---|---|---|---|"]
        for c in anec:
            L.append(f"| {c['id']} | {c['signal']} | {md_cell(c['claim'])} | "
                     f"{c['evidence']['count']} | {md_cell(c['admission_reason'])} |")
    else:
        L += ["_None._"]
    L += [""]

    L += [f"## Unexercised (ablation queue) ({len(doc['unexercised'])})", ""]
    if doc["unexercised"]:
        L += ["| what | name | reason |", "|---|---|---|"]
        for u in doc["unexercised"]:
            L.append(f"| {u['kind']} | `{u['name']}` | {md_cell(u['reason'])} |")
    else:
        L += ["_Nothing declared went unused in this window._"]
    L += ["",
          f"**Summary**: {doc['summary']['admissible']} admissible · "
          f"{doc['summary']['anecdotes']} anecdotes · {doc['summary']['unexercised']} unexercised", ""]
    return "\n".join(L)


def md_cell(s):
    return re.sub(r"\s+", " ", str(s)).replace("|", "\\|")


# --------------------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(
        prog="evolve_mine.py",
        description="Mine a finished cycle's artifacts for evolve candidates (deterministic; "
                    "the team-forge:evolve skill does the judging).")
    p.add_argument("path", nargs="?", help="the team hub (.claude/team-forge/<team>/) or the repo root")
    p.add_argument("--team", help="team name; required only when the repo holds more than one")
    p.add_argument("--ledger", help="ledger JSON (default: <hub>/tracker/status.json, falling back "
                                    "to docs/team-forge/<team>/final-ledger.json)")
    p.add_argument("--out", help="output dir (default: docs/team-forge/<team>/evolve/)")
    p.add_argument("--since", help="cycle id or ISO timestamp; mine only from there on")
    p.add_argument("--now", help="ISO timestamp to stamp as mined_at — makes output reproducible")
    p.add_argument("--memory-dir", action="append", default=[],
                   help="extra agent-memory root to mine (repeatable); the default is "
                        "<repo>/.claude/agent-memory/")
    p.add_argument("--register", help="lessons.md to dedupe against (default: "
                                      "docs/team-forge/<team>/lessons.md)")
    p.add_argument("--lint-register", metavar="PATH",
                   help="validate a lessons.md and exit 1 on a malformed register; mines nothing")
    p.add_argument("--json", action="store_true",
                   help="write the document to stdout as well; progress lines go to stderr")
    return p


def main(argv):
    global _OUT
    args = build_parser().parse_args(argv)
    if args.json:
        _OUT = sys.stderr
    if args.lint_register:
        return lint_register(args.lint_register)
    if not args.path:
        build_parser().print_usage(file=sys.stderr)
        print("✗ nothing to mine: pass a hub/repo path, or --lint-register", file=sys.stderr)
        return 2

    hub, repo_root, team = resolve_hub(args.path, args.team)
    kb = repo_root / "docs" / "team-forge" / team

    # --- inputs -------------------------------------------------------------
    if args.ledger:
        ledger_path = Path(args.ledger)
    else:
        live = hub / "tracker" / "status.json"
        archived = kb / "final-ledger.json"
        ledger_path = live if live.exists() else archived
        if not live.exists() and archived.exists():
            say(f"– live ledger absent (torn down); mining the archive {archived}")
    ledger = load_json(ledger_path, "ledger")
    design = load_yaml(hub / "design.yaml", "design.yaml")
    manifest = load_json(hub / "manifest.json", "manifest.json") if (hub / "manifest.json").exists() else {}

    mined_at = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date = mined_at[:10]
    out_dir = Path(args.out) if args.out else (kb / "evolve")

    events = ledger.get("events")
    if not isinstance(events, list):
        warn("ledger has no events[] list — mining what is left (budget, design, manifest)")
        events = []
    events = [e for e in events if isinstance(e, dict)]

    if args.since:
        events = apply_since(events, args.since)

    known = set(KNOWN_EVENT_KINDS)
    # Every place an archetype declares its own kinds. The two archetypes do not agree:
    # a workflow design writes `ledger.events` (the workflow fixtures), while a team design
    # writes `tracking.events_to_log` (templates/design.yaml.j2 line 159, and the
    # team-greeter fixture that follows it). Reading only `ledger.events` filed a team
    # design's ENTIRE documented vocabulary as lead-invented one-off nouns — the miner
    # accusing the lead of minting the exact kinds design.yaml told it to log, on every
    # team-archetype run. Union all four rather than pick a winner: both spellings are
    # already baked into designs on disk, and a rename would strand them.
    declared = []
    for block in ("ledger", "tracking"):
        cfg = design.get(block)
        if not isinstance(cfg, dict):
            continue
        for key in ("events", "events_to_log"):
            got = cfg.get(key)
            if isinstance(got, list):
                declared += got
    known |= {normalize_kind(k) for k in declared if isinstance(k, str)}
    known = {normalize_kind(k) for k in known}

    factor = DEFAULT_BUDGET_OVERRUN_FACTOR
    ev_cfg = design.get("evolve")
    if isinstance(ev_cfg, dict) and isinstance(ev_cfg.get("budget_overrun_factor"), (int, float)):
        factor = float(ev_cfg["budget_overrun_factor"])

    # --- mine ---------------------------------------------------------------
    cands = []
    for name, fn in (("recurrence", lambda: mine_recurrence(events, known, team)),
                     ("blocked_resolved", lambda: mine_blocked_resolved(events, team)),
                     ("gate_failure", lambda: mine_gate_failures(events, team)),
                     ("budget", lambda: mine_budget(ledger, factor, team)),
                     ("policy_adopted", lambda: mine_policies(events, team)),
                     ("lesson_event", lambda: mine_lesson_events(events, team)),
                     ("unknown_kind", lambda: mine_singletons(events, known, team))):
        try:
            cands += fn()
        except Exception as e:  # one bad payload must not cost the run its other lessons
            warn(f"signal '{name}' failed ({e.__class__.__name__}: {e}) — skipped, others continue")

    memory_files = discover_memory(repo_root, team, args.memory_dir)
    try:
        cands += mine_memory(memory_files, list(cands), team)
    except Exception as e:
        warn(f"memory mining failed ({e.__class__.__name__}: {e}) — skipped")

    # The blocked->resolved suggestion in SUGGESTION defaults to the lead's own MEMORY.md, and
    # only the workflow archetype reliably has one. `forge.py` gives native memory to roster
    # entries whose role is in DISPATCHED_MEMORY_ROLES (`advise`) plus the workflow lead it
    # emits on the `archetype: workflow` fork (`forge.py:1288` forks on this same key); a team
    # design's orchestrator gets `memory:` only if that roster entry sets it by hand, so
    # `.claude/agent-memory/<team>-lead/` normally never exists there. Left alone, every
    # blocked->resolved row on a team run pointed at a file that archetype never creates —
    # exactly the "path one archetype never emits" the skill's Step 2 warns the reader not to
    # work from. `references/layers.md` prescribes the fallback in so many words: on a team run
    # "a lesson that would have been a lead memory note lands in the register below, not in a
    # file this archetype never forged." The discovered-files half of the test is what keeps a
    # team design that DID set `memory:` on its orchestrator pointed at its real memory.
    lead_memory = f".claude/agent-memory/{team}-lead/MEMORY.md"
    lead_memory_exists = any(str(p).endswith(f"{team}-lead/MEMORY.md") for p in memory_files)
    if design.get("archetype") != "workflow" and not lead_memory_exists:
        for c in cands:
            if c["suggested_target"] == lead_memory:
                c["suggested_target"] = f"docs/team-forge/{team}/lessons.md"

    try:
        unexercised = mine_unexercised(design, manifest, events, repo_root, team)
    except Exception as e:
        warn(f"unexercised detection failed ({e.__class__.__name__}: {e}) — skipped")
        unexercised = []

    # --- stable order, then ids --------------------------------------------
    cands.sort(key=lambda c: (c["signal"], c["claim"]))
    register_path = Path(args.register) if args.register else (kb / "lessons.md")
    tables, ids, banner, _meta = parse_register(register_path)
    next_c, next_ll = next_ids(tables, ids)
    if not register_path.exists():
        say(f"– no register at {register_path} — C-ids start at C-{next_c:03d}")

    active = [(re.sub(r"[*`]", "", cell(r, "#")).strip(), cell(r, "lesson")) for r in tables["active"]]
    for i, c in enumerate(cands):
        c["id"] = f"C-{next_c + i:03d}"
        c.pop("_name", None)
        rel = sorted(lid for lid, text in active if lid and overlap(text, c["claim"]) >= 0.6)
        if rel:
            c["related_lessons"] = rel
            c["status"] = f"duplicate_of:{rel[0]}"
    # Second pass on purpose: a memory note can corroborate a candidate that sorts after it,
    # whose id the first pass has not written yet. The reference is dropped either way — it
    # points at a sibling candidate, and json.dumps refuses a cycle.
    for c in cands:
        src = c.pop("_corroborates", None)
        if src is not None:
            c["admission_reason"] = f"corroborates ledger candidate {src['id']} ({src['signal']})"

    adm = sum(1 for c in cands if c["admissible"])
    doc = {
        "schema": SCHEMA,
        "team": team,
        "mined_at": mined_at,
        "forge_version": manifest.get("forge_version") or FORGE_VERSION,
        "source": {
            "ledger": str(ledger_path),
            "events": len(events),
            "cycles": cycles_of(events),
            "memory_dirs": [str(Path(p).parent) for p in memory_files],
        },
        "register": {
            "path": str(register_path),
            "exists": register_path.exists(),
            "banner": banner,
            "active_ids": [lid for lid, _ in active if lid],
            "next_c_id": f"C-{next_c + len(cands):03d}",
            "next_lesson_id": f"LL-{next_ll}",
        },
        "candidates": cands,
        "unexercised": unexercised,
        "summary": {"admissible": adm, "anecdotes": len(cands) - adm, "unexercised": len(unexercised)},
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    jpath = out_dir / f"candidates-{date}.json"
    mpath = out_dir / f"candidates-{date}.md"
    jpath.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    mpath.write_text(render_md(doc, ledger_path))
    say(f"✓ mined {len(events)} events from {ledger_path}")
    say(f"✓ {adm} admissible · {len(cands) - adm} anecdotes · {len(unexercised)} unexercised")
    say(f"✓ {jpath}")
    say(f"✓ {mpath}  ← the skill reads this one")
    if args.json:
        print(json.dumps(doc, indent=2, sort_keys=True))
    return 0


def apply_since(events, since):
    """ISO prefixes filter by timestamp; anything else is treated as a cycle id and slices
    from the first event that names it. A --since nobody can resolve returns everything and
    says so — silently mining zero events is how a cycle loses its lessons."""
    if re.match(r"^\d{4}-\d{2}-\d{2}", since):
        return [e for e in events if str(e.get("ts") or "") >= since]
    for i, e in enumerate(events):
        pl = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        if since in {str(pl.get("cycle_id")), str(pl.get("cycle")), str(e.get("cycle_id"))}:
            return events[i:]
    warn(f"--since {since!r} matches no cycle id and is not an ISO timestamp — mining everything")
    return events


def cycles_of(events):
    seen = []
    for e in events:
        pl = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        cid = pl.get("cycle_id") or pl.get("cycle") or e.get("cycle_id")
        if isinstance(cid, str) and cid and cid not in seen:
            seen.append(cid)
    return seen


def discover_memory(repo_root, team, extra):
    """Native per-agent memory lives at <repo>/.claude/agent-memory/<agent>/MEMORY.md.
    --memory-dir points elsewhere (a fixture, an archived copy pulled off a torn-down run)."""
    # The `<team>-` prefix filter belongs to the DEFAULT root and only to it: that root holds
    # every team's memory, while a --memory-dir is a directory someone chose by hand and may
    # hold agents named anything. Truthiness-testing the flag inside one loop over all roots
    # dropped the filter from the default root the moment --memory-dir was passed, and every
    # other team's memory landed in this team's candidates.
    roots = [(repo_root / ".claude" / "agent-memory", True)] + [(Path(p), False) for p in extra]
    files = []
    for root, team_only in roots:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir() or not (d / "MEMORY.md").exists():
                continue
            if team_only and not d.name.startswith(f"{team}-"):
                continue
            files.append(d / "MEMORY.md")
    # Dedupe on the RESOLVED path, display the first spelling seen. Deduping on the raw string
    # let the same directory in under two spellings (`./.claude/agent-memory` passed as
    # --memory-dir alongside the default root), which mined every note twice and would have
    # proposed one lesson as two.
    seen, uniq = set(), []
    for f in files:
        try:
            key = str(f.resolve())
        except OSError:
            key = str(f)
        if key not in seen:
            seen.add(key)
            uniq.append(str(f))
    return sorted(uniq)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
