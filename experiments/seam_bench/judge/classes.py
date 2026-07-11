"""Judge classes — plan v2.1 §5.3 (view decorrelation) and
SEAM_AUTOTRAINING_PLAN.md §3.2.

Three judge classes vote in one panel, each decorrelated from the others
by *what it is structurally allowed to see*, not by convention:

- **J-fwd** — sees (paraphrased intent, sanitized G). Each fwd seat gets a
  different paraphrase (a separate stateless, cached call) so surface-cue
  anchoring decorrelates across same-model seats.
- **J-back** — sees G ONLY. It writes the intent G encodes; a *separate*
  stateless comparator call scores that reconstruction against the real
  intent. The reconstruction step's function signature has no ``intent``
  parameter at all — that is the enforcement mechanism, not a comment
  promising isolation.
- **J-probe** — an LLM compiles intent fragments into concrete probe
  queries; the *verdict* is deterministic reachability/response checking
  over G's per-role EFSM (no sampling anywhere in the verdict path). The
  compiler call never sees G at all, only the intent plus the protocol's
  role/message vocabulary (safe metadata, not payload text).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from stjp_core.compiler.efsm_parser import EFSM, get_efsm_from_scribble
from stjp_core.config import SCRIBBLE_PATH

from experiments.seam_bench.judge.aggregate import verify_evidence
from experiments.seam_bench.judge.cache import VerdictCache, cache_key, hash_text
from experiments.seam_bench.judge.payloads import SanitizedPayload
from experiments.seam_bench.judge.seats import (
    AnthropicLike,
    Evidence,
    SeatConfig,
    VERDICT_SCHEMA,
    Verdict,
    call_structured,
    call_text,
    verdict_from_raw,
)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_PARAPHRASE_SYSTEM = (
    "You paraphrase a short task description. Preserve every requirement, "
    "constraint, and role mention exactly in meaning; change only surface "
    "wording, sentence structure, and register. Do not add or drop any "
    "requirement. Reply with the paraphrase only, no preamble."
)

_FWD_RUBRIC_LINES = {
    "roles": "Pay special attention to whether every role the intent implies is present and does the right thing.",
    "ordering": "Pay special attention to whether the message ordering matches what the intent implies.",
    "prohibitions": "Pay special attention to whether anything the intent forbids is nonetheless possible in the protocol.",
    "termination": "Pay special attention to whether the protocol terminates the way the intent implies it should.",
}

_FWD_SYSTEM_TEMPLATE = (
    "You are one independent judge on a panel checking whether a formal "
    "coordination protocol (Scribble global protocol G) faithfully "
    "implements a natural-language task intent. You do not know how many "
    "other judges exist, what they voted, or anything about how G was "
    "produced. Judge only from the INTENT and PROTOCOL given below.\n\n"
    "{rubric_line}\n\n"
    "Vote yes if the protocol faithfully realizes the intent, no if it "
    "does not, or abstain if the intent is too underspecified here to "
    "judge. Every evidence quote must be copied verbatim from the INTENT "
    "or PROTOCOL text you were given — do not paraphrase evidence."
)

_BACK_RECONSTRUCT_SYSTEM = (
    "You are a judge on a faithfulness panel. Below is ONLY a formal "
    "coordination protocol (Scribble global protocol G) — you have not "
    "seen and will never see the original task description it was "
    "translated from. Write, in 2-5 plain sentences, the task intent you "
    "believe this protocol implements: who the roles are, what they "
    "exchange, in what order, and any prohibitions or termination "
    "conditions implied by its structure. Reply with the reconstruction "
    "only, no preamble."
)

_BACK_COMPARE_SYSTEM = (
    "You compare two natural-language task descriptions: an ORIGINAL "
    "intent and a RECONSTRUCTION independently written by someone who "
    "only saw a formal protocol, never the original. Vote yes if the "
    "reconstruction captures the same coordination requirements as the "
    "original (roles, ordering, prohibitions, termination), no if it "
    "misses or contradicts something material, or abstain if the "
    "original is too underspecified to compare against. Every evidence "
    "quote must be copied verbatim from the ORIGINAL or the "
    "RECONSTRUCTION text given below — label ORIGINAL quotes as "
    "source=\"intent\"; do not cite the protocol, you were never shown it."
)

_PROBE_COMPILE_SYSTEM = (
    "You translate a task intent into concrete, checkable coordination "
    "queries about a protocol between fixed roles. You do not see the "
    "protocol itself — only its role names and message vocabulary. For "
    "each query, choose ONE of:\n"
    "  - \"reachable\": some execution lets ROLE (direction, LABEL) with PEER happen\n"
    "  - \"never\": no execution should let ROLE (direction, LABEL) with PEER happen\n"
    "  - \"response\": whenever ROLE (direction, LABEL) with PEER happens, "
    "ROLE must later (direction2, LABEL2) with PEER2 in the same role's "
    "trace\n"
    "Use ONLY roles from ALLOWED_ROLES and labels from ALLOWED_LABELS "
    "below — do not invent names. Leave unused response_* fields as empty "
    "strings. Compile at most 6 probes, only for clauses of the intent "
    "that are mechanically checkable this way; skip clauses that aren't."
)


def _paraphrase_prompt_hash(slot: int) -> str:
    return hash_text(f"{_PARAPHRASE_SYSTEM}\x00slot={slot}")


def generate_paraphrase(client: AnthropicLike, cache: VerdictCache, seat: SeatConfig, intent: str) -> str:
    key = cache_key("paraphrase", seat.model_id, seat.temperature, _paraphrase_prompt_hash(seat.paraphrase_slot), hash_text(intent))

    def compute() -> str:
        user = f"Paraphrase variant #{seat.paraphrase_slot}:\n\n{intent}"
        return call_text(client, seat.model_id, seat.temperature, _PARAPHRASE_SYSTEM, user, max_tokens=512)

    return cache.get_or_compute(key, compute)


# ---------------------------------------------------------------------------
# J-fwd
# ---------------------------------------------------------------------------


def run_j_fwd(
    client: AnthropicLike,
    cache: VerdictCache,
    seat: SeatConfig,
    intent: str,
    payload: SanitizedPayload,
) -> Verdict:
    assert seat.class_ == "fwd"
    paraphrase = generate_paraphrase(client, cache, seat, intent)
    system = _FWD_SYSTEM_TEMPLATE.format(rubric_line=_FWD_RUBRIC_LINES[seat.rubric_emphasis])
    prompt_hash = hash_text(system)

    user = f"INTENT:\n{paraphrase}\n\nPROTOCOL:\n{payload.text}"

    def compute_at(temperature: float) -> Verdict:
        key = cache_key(seat.class_, seat.model_id, temperature, prompt_hash, hash_text(user))
        data = cache.get_or_compute(key, lambda: call_structured(client, seat.model_id, temperature, system, user, VERDICT_SCHEMA, seat.max_tokens))
        temp_seat = SeatConfig(**{**seat.__dict__, "temperature": temperature})
        return verdict_from_raw(data, temp_seat)

    verdict = compute_at(seat.temperature)
    ok, fabricated = verify_evidence(verdict, payload.text, paraphrase)
    if not ok:
        resampled = compute_at(seat.resample_temp())
        ok2, fabricated2 = verify_evidence(resampled, payload.text, paraphrase)
        if not ok2:
            resampled.discarded = True
            resampled.discard_reason = f"fabricated evidence after resample: {fabricated2}"
        return resampled
    return verdict


# ---------------------------------------------------------------------------
# J-back
# ---------------------------------------------------------------------------


def reconstruct_intent(client: AnthropicLike, cache: VerdictCache, seat: SeatConfig, payload: SanitizedPayload) -> str:
    """Blind round-trip step. Note this function does not take an
    ``intent`` argument at all — that is what makes it structurally
    immune to confirmation bias, not a promise in a docstring."""
    prompt_hash = hash_text(_BACK_RECONSTRUCT_SYSTEM)
    key = cache_key("back_reconstruct", seat.model_id, seat.temperature, prompt_hash, payload.payload_hash)

    def compute() -> str:
        return call_text(client, seat.model_id, seat.temperature, _BACK_RECONSTRUCT_SYSTEM, payload.text, max_tokens=512)

    return cache.get_or_compute(key, compute)


def compare_intents(
    client: AnthropicLike,
    cache: VerdictCache,
    seat: SeatConfig,
    original_intent: str,
    reconstructed_intent: str,
    temperature: float | None = None,
) -> Verdict:
    temperature = seat.temperature if temperature is None else temperature
    prompt_hash = hash_text(_BACK_COMPARE_SYSTEM)
    user = f"ORIGINAL:\n{original_intent}\n\nRECONSTRUCTION:\n{reconstructed_intent}"
    key = cache_key("back_compare", seat.model_id, temperature, prompt_hash, hash_text(user))

    def compute() -> dict:
        return call_structured(client, seat.model_id, temperature, _BACK_COMPARE_SYSTEM, user, VERDICT_SCHEMA, seat.max_tokens)

    data = cache.get_or_compute(key, compute)
    temp_seat = SeatConfig(**{**seat.__dict__, "temperature": temperature})
    return verdict_from_raw(data, temp_seat)


def run_j_back(
    client: AnthropicLike,
    cache: VerdictCache,
    seat: SeatConfig,
    intent: str,
    payload: SanitizedPayload,
) -> Verdict:
    assert seat.class_ == "back"
    reconstructed = reconstruct_intent(client, cache, seat, payload)

    def compute_at(temperature: float) -> Verdict:
        return compare_intents(client, cache, seat, intent, reconstructed, temperature)

    verdict = compute_at(seat.temperature)
    # The comparator never saw G, so any evidence it cites as
    # source="protocol" is fabricated by construction; protocol_text="" makes
    # verify_evidence correctly flag that.
    ok, fabricated = verify_evidence(verdict, "", intent + " " + reconstructed)
    if not ok:
        resampled = compute_at(seat.resample_temp())
        ok2, fabricated2 = verify_evidence(resampled, "", intent + " " + reconstructed)
        if not ok2:
            resampled.discarded = True
            resampled.discard_reason = f"fabricated evidence after resample: {fabricated2}"
        return resampled
    return verdict


# ---------------------------------------------------------------------------
# J-probe — interface + deterministic checker
# ---------------------------------------------------------------------------

ProbeKind = Literal["reachable", "never", "response"]
ProbeDirection = Literal["send", "receive"]

PROBE_COMPILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "probes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query_text": {"type": "string"},
                    "kind": {"type": "string", "enum": ["reachable", "never", "response"]},
                    "role": {"type": "string"},
                    "label": {"type": "string"},
                    "direction": {"type": "string", "enum": ["send", "receive"]},
                    "peer": {"type": "string"},
                    "response_role": {"type": "string"},
                    "response_label": {"type": "string"},
                    "response_direction": {"type": "string", "enum": ["send", "receive"]},
                    "response_peer": {"type": "string"},
                },
                "required": [
                    "query_text", "kind", "role", "label", "direction", "peer",
                    "response_role", "response_label", "response_direction", "response_peer",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["probes"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ProbeSpec:
    """The deterministic, compiled half of a probe: {query, compiled_check}
    where ``compiled_check`` is this structured spec, not an LLM."""

    kind: ProbeKind
    role: str
    label: str
    direction: ProbeDirection
    peer: str = ""
    response_role: str = ""
    response_label: str = ""
    response_direction: ProbeDirection | str = ""
    response_peer: str = ""


@dataclass(frozen=True)
class Probe:
    query_text: str
    compiled_check: ProbeSpec


@dataclass
class ProbeResult:
    probe: Probe
    passed: bool
    counterexample: list[str] = field(default_factory=list)
    note: str = ""


def compile_probes_from_intent(
    client: AnthropicLike,
    cache: VerdictCache,
    seat: SeatConfig,
    intent: str,
    roles: list[str],
    message_labels: list[str],
) -> list[Probe]:
    """The one LLM call in J-probe. It never sees G — only the intent and
    the protocol's role/label vocabulary (safe, comment-free metadata
    already extracted by the sanitizer)."""
    user = (
        f"ALLOWED_ROLES: {', '.join(roles)}\n"
        f"ALLOWED_LABELS: {', '.join(message_labels)}\n\n"
        f"INTENT:\n{intent}"
    )
    prompt_hash = hash_text(_PROBE_COMPILE_SYSTEM)
    key = cache_key("probe_compile", seat.model_id, seat.temperature, prompt_hash, hash_text(user))

    def compute() -> dict:
        return call_structured(client, seat.model_id, seat.temperature, _PROBE_COMPILE_SYSTEM, user, PROBE_COMPILE_SCHEMA, seat.max_tokens)

    data = cache.get_or_compute(key, compute)

    role_set = set(roles)
    label_set = set(message_labels)
    probes: list[Probe] = []
    for item in data.get("probes", []):
        if item["role"] not in role_set or item["label"] not in label_set:
            continue
        if item["kind"] == "response":
            if item["response_role"] not in role_set or item["response_label"] not in label_set:
                continue
        spec = ProbeSpec(
            kind=item["kind"],
            role=item["role"],
            label=item["label"],
            direction=item["direction"],
            peer=item.get("peer", ""),
            response_role=item.get("response_role", ""),
            response_label=item.get("response_label", ""),
            response_direction=item.get("response_direction", ""),
            response_peer=item.get("response_peer", ""),
        )
        probes.append(Probe(query_text=item["query_text"], compiled_check=spec))
    return probes


def _label_char(direction: str) -> str:
    return "!" if direction == "send" else "?"


def _transition_matches(t, label: str, direction: str, peer: str) -> bool:
    if t.label != label or t.direction != direction:
        return False
    if peer and t.peer != peer:
        return False
    return True


def _enumerate_paths(efsm: EFSM, max_depth: int = 200, max_paths: int = 2000):
    """Bounded DFS over role-EFSM transitions from the initial state.
    Each state may be revisited a small number of times so a loop's body
    is represented at least once without risking unbounded blow-up on
    recursive protocols. Deterministic, no sampling."""
    paths: list[list] = []
    start = efsm.initial_state
    if not start:
        return paths

    def dfs(state: str, path: list, visit_counts: dict):
        if len(paths) >= max_paths:
            return
        outgoing = efsm.transitions_from(state)
        if not outgoing or len(path) >= max_depth:
            paths.append(list(path))
            return
        for t in outgoing:
            count = visit_counts.get(t.target, 0)
            if count >= 2:
                # Loop closed enough times to have exercised its body; stop
                # here rather than expanding forever.
                paths.append(list(path) + [t])
                continue
            visit_counts[t.target] = count + 1
            dfs(t.target, path + [t], visit_counts)
            visit_counts[t.target] = count

    dfs(start, [], {start: 1})
    return paths


def evaluate_probe(efsms: dict[str, EFSM], probe: Probe) -> ProbeResult:
    spec = probe.compiled_check
    efsm = efsms.get(spec.role)
    if efsm is None:
        return ProbeResult(probe=probe, passed=False, note=f"unknown role {spec.role!r}")

    def trace_labels(path: list) -> list[str]:
        return [f"{t.peer}{_label_char(t.direction)}{t.label}" for t in path]

    if spec.kind in ("reachable", "never"):
        found = any(
            _transition_matches(t, spec.label, spec.direction, spec.peer)
            for t in efsm.transitions
        )
        if spec.kind == "reachable":
            return ProbeResult(probe=probe, passed=found, note="" if found else "label never appears in the EFSM")
        else:  # never
            return ProbeResult(probe=probe, passed=not found, note="" if not found else "label reachable despite prohibition")

    # response
    paths = _enumerate_paths(efsm)
    if not paths:
        return ProbeResult(probe=probe, passed=True, note="role has no reachable transitions; trigger vacuously unreachable")

    saw_trigger_anywhere = False
    for path in paths:
        trigger_idx = None
        for i, t in enumerate(path):
            if _transition_matches(t, spec.label, spec.direction, spec.peer):
                trigger_idx = i
                saw_trigger_anywhere = True
                break
        if trigger_idx is None:
            continue
        response_ok = any(
            _transition_matches(t, spec.response_label, spec.response_direction, spec.response_peer)
            for t in path[trigger_idx + 1:]
        )
        if not response_ok:
            return ProbeResult(
                probe=probe,
                passed=False,
                counterexample=trace_labels(path),
                note="trigger occurs without the required response later on the same path",
            )

    if not saw_trigger_anywhere:
        return ProbeResult(probe=probe, passed=True, note="trigger never occurs in any enumerated path (vacuously satisfied)")
    return ProbeResult(probe=probe, passed=True)


def build_efsms_from_source(protocol_source: str, protocol_name: str, roles: list[str]) -> dict[str, EFSM]:
    """Build per-role EFSMs by running the REAL Scribble CLI (hard
    toolchain mandate — never a Python-only approximation). Takes the
    original G source (with its ``data <java> ...`` header, which the
    sanitizer intentionally strips), not the sanitized payload — J-probe's
    verdict is code, not an LLM reading text, so there is nothing here for
    a comment to persuade; sanitization only matters for the classes that
    put G in front of a model."""
    if not SCRIBBLE_PATH.exists():
        raise RuntimeError(
            "Real Scribble toolchain not found at "
            f"{SCRIBBLE_PATH}. Run tools/setup_scribble_cloud.sh — "
            "J-probe refuses to fall back to a Python-only approximation."
        )
    import re
    import shutil
    import tempfile

    # Scribble's CLI requires the file's basename to match the source's
    # `module <name>;` declaration ("Simple module name ... mismatch").
    module_match = re.search(r"module\s+(\w+)\s*;", protocol_source)
    module_name = module_match.group(1) if module_match else "seam_bench_probe"

    tmp_dir = Path(tempfile.mkdtemp(dir=str(SCRIBBLE_PATH.parent.parent)))
    tmp_path = tmp_dir / f"{module_name}.scr"
    tmp_path.write_text(protocol_source, encoding="utf-8")
    try:
        return {role: get_efsm_from_scribble(tmp_path, protocol_name, role) for role in roles}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_j_probe(
    client: AnthropicLike,
    cache: VerdictCache,
    seat: SeatConfig,
    compiler_seat: SeatConfig,
    intent: str,
    payload: SanitizedPayload,
    efsms: dict[str, EFSM],
) -> tuple[Verdict, list[ProbeResult]]:
    """Compiles probes (one stateless LLM call, cached) then evaluates
    them deterministically. The returned Verdict carries no sampled
    content — confidence is always 1.0 and evidence is exempt from the
    §5.4 string-match check (see ``verify_evidence`` docstring)."""
    probes = compile_probes_from_intent(client, cache, compiler_seat, intent, payload.roles, payload.message_labels)
    results = [evaluate_probe(efsms, p) for p in probes]

    if not results:
        vote = "abstain"
    elif any(not r.passed for r in results):
        vote = "no"
    else:
        vote = "yes"

    evidence = [Evidence(quote=r.probe.query_text, source="protocol") for r in results]
    missing = [
        f"{r.probe.query_text} :: {r.note}" + (f" counterexample={r.counterexample}" if r.counterexample else "")
        for r in results
        if not r.passed
    ]
    verdict = Verdict(
        vote=vote,
        confidence=1.0,
        evidence=evidence,
        missing=missing,
        seat_id=seat.seat_id,
        class_="probe",
        model_id=seat.model_id,
        temperature=0.0,
        weight=seat.weight,
    )
    return verdict, results
