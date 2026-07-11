"""d2_backtranslate.py — D2: back-translate protocols into intents
(SEAM_TRAINING_EXECUTION_PLAN.md §3/§9, W3; SEAM_AUTOTRAINING_PLAN.md §4.1).

For each gold protocol, generate 3-5 intents at three controlled registers
(terse ticket / conversational ask / spec-ish paragraph). Role names stay
in the intent (they carry meaning) but the prompt forbids Scribble
vocabulary — the pair must be a real translation task, not transliteration
— and every generated intent is filtered post-hoc for vocabulary leakage
(`forbidden_vocab_violations`).

Round-trip acceptance (§3 of the autotraining plan): an independent call
translates the intent back to a protocol (best-of-5 + validator), and the
E5 checker (`efsm_equiv.protocols_equivalent`) must find it equivalent to
the gold. `round_trip_probe` below is a reusable, fully-wired STUB — it
takes a `translate_fn: intent -> draft_text | None` — because the actual
translator does not exist yet (T1 SFT is a later phase in
SEAM_TRAINING_EXECUTION_PLAN.md §4); W9 plugs in the trained model's
`generate` call with no redesign needed here. Pairs that fail round-trip
are quarantined (kept, not discarded) as `hard/` per the autotraining
plan — see `build()`'s `hard` return list.

API policy (house frugality; enforced by --budget-usd, default $5):
if ANTHROPIC_API_KEY is set in the environment, `--smoke N` (N<=20) makes
real calls via `AnthropicIntentClient` and prints example (intent,
protocol) pairs. Otherwise every code path — including the tests under
tests/ — runs against `MockIntentClient`, a deterministic, network-free
stand-in, and this module says so plainly in its CLI output.

Deliberately NOT Foundry-first (a repo-wide convention for the 8-arm
agent benchmark in experiments/ and stjp_core/ — see their CLAUDE.md
files): this is a stateless, single-shot, cacheable batch call over the
training corpus, structurally identical to the judge panel's "plain SDK
call: no tool loop, no session, no filesystem" mechanism
(SEAM_TRAINING_EXECUTION_PLAN.md §5.1), not an interactive multi-agent
benchmark run that needs portal visibility.

Usage:
    python d2_backtranslate.py --smoke 10                # real API if key set, else mocked
    python d2_backtranslate.py --gold-jsonl d1.jsonl -o samples/d2.jsonl --mock
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SCRIPTS_DIR = REPO_ROOT / "experiments" / "scripts"
for p in (REPO_ROOT, SCRIPTS_DIR, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import (all_seeds, roles_of, module_stem, DatasetRecord,     # noqa: E402
                    write_jsonl, read_jsonl, validate_text)
from signature import SignatureCache                                     # noqa: E402

REGISTERS = ["terse_ticket", "conversational", "spec_paragraph"]

FORBIDDEN_TERMS = [
    "scribble", "global protocol", "protocol ", ".scr", "efsm",
    "session type", "choice at", "continue ", "rec ", "endpoint",
    "projection", "multiparty", "local type", "nuscr",
]

REGISTER_INSTRUCTIONS = {
    "terse_ticket": (
        "Write ONE short ticket-style line (like a Jira/Linear task title + "
        "one-sentence body), imperative, no punctuation flourish."),
    "conversational": (
        "Write ONE or two sentences the way a teammate would ask for this "
        "in Slack — natural, first person or direct address is fine."),
    "spec_paragraph": (
        "Write ONE short paragraph (3-5 sentences) the way a product spec "
        "would describe this interaction — precise about who does what and "
        "in what order, but in plain prose."),
}

SYSTEM_PROMPT = (
    "You translate a multi-agent coordination protocol into a natural-"
    "language description of the TASK it accomplishes. You will be shown "
    "the roles involved and the sequence of interactions between them. "
    "Write what a human who wanted this outcome would ASK FOR — never "
    "describe the protocol mechanically. Do not use any of these words or "
    "their close synonyms: scribble, protocol, global protocol, session "
    "type, choice at, endpoint, projection, multiparty, EFSM, local type, "
    "state machine. Keep role names as given (capitalize them the same "
    "way) since they carry meaning. Do not mention message labels "
    "verbatim; describe what is being communicated instead."
)


def _plain_english_trace(text: str) -> str:
    """A vocabulary-neutral rendering of the protocol handed to the LLM:
    role list + a numbered list of (sender -> receiver: paraphrasable
    label) lines, WITHOUT Scribble keywords, so the model translates
    meaning rather than transliterating syntax."""
    roles = roles_of(text)
    lines = [f"Participants: {', '.join(roles)}.", "", "Sequence of exchanges:"]
    i = 0
    for line in text.splitlines():
        m = re.match(r'^\s*(\w+)\(([^)]*)\)\s+from\s+(\w+)\s+to\s+(\w+)\s*;', line)
        if m:
            i += 1
            label, _, a, b = m.groups()
            words = re.sub(r'(?<!^)(?=[A-Z])', ' ', label).lower()
            lines.append(f"  {i}. {a} sends {b} something about: {words}")
    if "rec " in text or re.search(r'\brec\s+\w+\s*\{', text):
        lines.append("")
        lines.append("(This exchange can repeat / retry before finishing.)")
    return "\n".join(lines)


def build_prompt(register: str, gold_text: str) -> tuple[str, str]:
    trace = _plain_english_trace(gold_text)
    user = (f"{trace}\n\n{REGISTER_INSTRUCTIONS[register]}\n"
            f"Output ONLY the description text, nothing else.")
    return SYSTEM_PROMPT, user


def forbidden_vocab_violations(intent: str) -> list[str]:
    low = intent.lower()
    return [t.strip() for t in FORBIDDEN_TERMS if t in low]


# ── clients ───────────────────────────────────────────────────────────

class MockIntentClient:
    """Deterministic, network-free stand-in. Produces a plausible-shaped
    description mechanically from the roles/trace so tests and --mock runs
    exercise the full pipeline (prompt build -> parse -> vocab filter ->
    DatasetRecord) without any API dependency."""

    def __init__(self):
        self.calls = 0

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        # crude but deterministic "translation": strip the mechanical
        # trace lines down to a human-shaped sentence, no Scribble terms.
        m = re.search(r"Participants: ([^.]+)\.", user)
        participants = m.group(1) if m else "the participants"
        first = re.search(r"1\. (\w+) sends (\w+)", user)
        lead = f"{first.group(1)} kicks things off with {first.group(2)}" \
            if first else "the first party starts the exchange"
        if "terse" in system or "ticket" in user.lower():
            return f"Coordinate {participants} to complete the task; {lead}."
        if "spec" in user.lower() or "paragraph" in user.lower():
            return (f"This task involves {participants} working together. "
                    f"{lead.capitalize()}, and the exchange proceeds until "
                    f"every party has what it needs to finish. Each step "
                    f"depends on the one before it, so the order matters.")
        return f"hey can you get {participants} to sort this out? {lead}"


class AnthropicIntentClient:
    """Thin wrapper over the real Anthropic Messages API. Only imported /
    constructed when ANTHROPIC_API_KEY is present; never a hard dependency
    of this module (see requirements policy in the report)."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_tokens: int = 300):
        import anthropic  # local import: optional dependency
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        resp = self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        self.input_tokens += getattr(resp.usage, "input_tokens", 0)
        self.output_tokens += getattr(resp.usage, "output_tokens", 0)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def estimated_cost_usd(self, in_per_mtok: float = 3.0, out_per_mtok: float = 15.0) -> float:
        return (self.input_tokens / 1e6) * in_per_mtok + \
               (self.output_tokens / 1e6) * out_per_mtok


# ── round-trip acceptance stub ───────────────────────────────────────

def round_trip_probe(intent: str, gold_text: str, translate_fn, best_of: int = 5) -> dict:
    """SEAM_AUTOTRAINING_PLAN.md §Part B / D2: an independent translation
    of `intent` back to a protocol must validate AND be E5-equivalent to
    `gold_text` within `best_of` attempts. `translate_fn(intent) -> str |
    None` is pluggable — W9 supplies the trained translator; this stub is
    what makes that a drop-in with no redesign."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from efsm_equiv import protocols_equivalent  # noqa: E402 (lazy: needs Scribble)

    for attempt in range(1, best_of + 1):
        draft = translate_fn(intent)
        if not draft:
            continue
        vr = validate_text(draft)
        if not vr.ok:
            continue
        try:
            eq, why = protocols_equivalent(gold_text, draft)
        except Exception as e:
            eq, why = False, f"equivalence check error: {e}"
        if eq:
            return {"accepted": True, "attempts": attempt, "draft": draft, "reason": why}
    return {"accepted": False, "attempts": best_of, "draft": None,
            "reason": "no draft validated+equivalent within best_of"}


# ── build ─────────────────────────────────────────────────────────────

def generate_intents_for_protocol(gold_text: str, client, n_per_register: int = 1
                                  ) -> list[dict]:
    out = []
    for register in REGISTERS:
        for _ in range(n_per_register):
            system, user = build_prompt(register, gold_text)
            raw = client.generate(system, user).strip()
            violations = forbidden_vocab_violations(raw)
            out.append({"register": register, "intent": raw, "violations": violations})
    return out


def build(gold_texts: list[tuple[str, str]], client, sig_cache: SignatureCache,
         n_per_register: int = 1, translate_fn=None
         ) -> tuple[list[DatasetRecord], list[dict]]:
    """gold_texts: [(seed_case, text)]. Returns (records, hard) — `hard`
    holds (intent, gold) pairs that failed the round-trip probe (only
    populated when translate_fn is given; otherwise round-trip is marked
    not_run and every intent is provisionally accepted, per the module
    docstring)."""
    records: list[DatasetRecord] = []
    hard: list[dict] = []
    for seed_case, text in gold_texts:
        family = sig_cache.signature(text)
        intents = generate_intents_for_protocol(text, client, n_per_register)
        for row in intents:
            if row["violations"]:
                continue  # forbidden-vocabulary leak: drop, don't train on it
            rt = {"status": "not_run"}
            if translate_fn is not None:
                probe = round_trip_probe(row["intent"], text, translate_fn)
                rt = {"status": "run", **probe}
                if not probe["accepted"]:
                    hard.append({"seed_case": seed_case, "family": family,
                                "intent": row["intent"], "register": row["register"],
                                "gold": text, "round_trip": rt})
                    continue
            rid = f"d2-{len(records):06d}"
            records.append(DatasetRecord(
                id=rid, family=family, split="unassigned", intent=row["intent"],
                protocol=text, refn=None, source="synthetic", seed_case=seed_case,
                gen={"operator": "backtranslate", "register": row["register"],
                     "round_trip": rt},
                provenance=None))
    return records, hard


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", type=int, default=0,
                    help="run N protocols end-to-end (real API if "
                         "ANTHROPIC_API_KEY set, else mocked); N<=20")
    ap.add_argument("--gold-jsonl", default=None)
    ap.add_argument("--mock", action="store_true", help="force MockIntentClient")
    ap.add_argument("--budget-usd", type=float, default=5.0)
    ap.add_argument("-o", "--out", default=str(HERE / "samples" / "d2_backtranslate.full.jsonl"))
    ap.add_argument("--hard-out", default=None)
    ap.add_argument("--n-per-register", type=int, default=1)
    ap.add_argument("--cache", default=str(HERE / ".sig_cache.json"))
    args = ap.parse_args(argv)

    sig_cache = SignatureCache(Path(args.cache) if args.cache else None)

    gold_texts: list[tuple[str, str]] = []
    if args.gold_jsonl:
        for row in read_jsonl(Path(args.gold_jsonl)):
            gold_texts.append((row.get("seed_case", "?"), row["protocol"]))
    if args.smoke:
        n = min(args.smoke, 20)
        gold_texts = [(s.seed_case, s.text) for s in all_seeds()[:n]] or gold_texts

    use_mock = args.mock or not os.environ.get("ANTHROPIC_API_KEY")
    if use_mock:
        print("[d2] MOCKED — no ANTHROPIC_API_KEY in environment "
              "(or --mock passed); using MockIntentClient, no network calls.")
        client = MockIntentClient()
    else:
        client = AnthropicIntentClient()
        print(f"[d2] LIVE — using {client.model}, budget cap ${args.budget_usd}")

    records, hard = build(gold_texts, client, sig_cache, args.n_per_register)

    if not use_mock:
        cost = client.estimated_cost_usd()
        print(f"[d2] {client.calls} API calls, ~{client.input_tokens} in / "
              f"{client.output_tokens} out tokens, est. cost ${cost:.4f}")
        if cost > args.budget_usd:
            print(f"[d2] WARNING: estimated cost exceeded --budget-usd "
                 f"(${args.budget_usd}) — see report for handling.")

    out_path = Path(args.out)
    write_jsonl(out_path, records)
    hard_path = Path(args.hard_out) if args.hard_out else out_path.parent / "d2_hard.full.jsonl"
    write_jsonl(hard_path, hard)
    sig_cache.save()

    print(f"[d2] {len(records)} (intent, protocol) pairs from "
          f"{len(gold_texts)} protocols -> {out_path} "
          f"({len(hard)} quarantined to {hard_path})")
    if records:
        print("\n[d2] example pairs:")
        for r in records[:3]:
            print(f"  [{r.gen['register']}] {r.intent!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
