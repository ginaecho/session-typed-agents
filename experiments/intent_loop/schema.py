"""schema.py — typed artifacts of the intent-interrogation loop.

The loop (BENCHMARK_PLAN_V3 §10.3 called this "the interrogation step" and
modeled it as a one-shot distillation; this app makes it a real multi-turn
Q&A) produces four artifact families, all defined here so every module and
the corpus JSONL agree on one shape:

  Requirement / DistilledIntent  what interrogation extracts. Requirements
      are ATOMIC and TYPED (ordering / authorization / value / branch /
      termination / role) because the faithfulness suite checks them one by
      one against the drafted protocol — a single prose blob cannot be
      checked item-wise, a typed checklist can.
  QA / InterrogationResult       the Q&A transcript (audit trail: which
      requirement came from the document vs. from an answer vs. remained
      an explicit assumption).
  FaithfulnessReport             per-requirement coverage + back-translation
      comparison + optional gold EFSM-equivalence, with the aggregate
      verdict rule stated in faithfulness.py.
  LoopRecord                     one corpus row = one full loop episode
      (intent -> dialogue -> distilled -> draft attempts -> final protocol
      -> faithfulness). This is the training corpus for both prompt
      optimization (optimize.py, no weight updates) and any later SFT run
      (SEAM_TRAINING_EXECUTION_PLAN.md).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

REQUIREMENT_KINDS = (
    "role",           # a participant and what it is responsible for
    "ordering",       # X must happen before Y
    "authorization",  # X may only happen after approval by R
    "value",          # a payload constraint (threshold, non-empty, enum)
    "branch",         # a decision point and who decides it
    "termination",    # how the session ends / who learns the outcome
    "invariant",      # a counter/budget that must hold across the session
    "policy",         # NOT expressible as a protocol — see POLICY_KIND
    "interior",       # deliberately NOT protocol — see INTERIOR_KIND
    "other",
)

#: Work that happens INSIDE one role and crosses no boundary: reading a
#: traceback, editing a file, choosing which cell to fix. It is real and
#: often most of a document, but it is the untyped interior of an agent —
#: the `dyn` participant of gradual session typing — and a protocol has
#: nothing to say about it.
#:
#: This kind exists because grading it was making the faithfulness number a
#: lie in the opposite direction from the old policy bug: a checklist full
#: of intra-role procedure can never be "realized" by any protocol, so
#: recall was reporting a failure of the drafter where the honest reading is
#: "most of this document is not coordination at all". Forcing it into the
#: protocol would be over-protocolization; scoring the protocol on it is
#: simply wrong. Reported, never graded.
INTERIOR_KIND = "interior"

#: How much it matters that the protocol realizes this.
#:
#: Demanding 100% of a 20-item checklist is the wrong bar: a real document
#: mixes obligations that MUST hold (the act a role may not perform without
#: approval; the evidence a verdict may not be issued without) with detail
#: that is merely desirable (which structured fields a payload carries).
#: Scoring them equally produced "3 of 19" — a number that says a protocol
#: is 16% right when it might have every obligation covered and be missing
#: only conveniences, or the reverse, which is a catastrophe. So the verdict
#: turns on MUST alone, and the rest is reported.
#:
#:   must    an obligation or a hard constraint. If this is unmet the
#:           protocol is wrong — an unauthorized act becomes possible, or a
#:           decision can be taken on absent evidence.
#:   should  intended and expected, but its absence does not make the
#:           protocol unsafe (a field left opaque, a distinction blurred).
#:   nice    detail, elaboration, convenience.
PRIORITIES = ("must", "should", "nice")
DEFAULT_PRIORITY = "should"

#: Requirements a multiparty session type structurally CANNOT express, and
#: which must therefore be enforced outside the protocol layer (deployment,
#: identity/IAM, retention, org policy). The canonical example, observed on
#: the first live episode: "the FinanceApprover and the PaymentProcessor
#: must be distinct people." A session type constrains ROLES and the
#: messages between them; which principal inhabits a role is invisible to
#: it. Grading such a requirement against the protocol would be a category
#: error — the honest verdict is "no protocol can satisfy this", not "the
#: drafter failed".
#:
#: The classification is made at DISTILL time, by the interrogator, before
#: any protocol exists — so it can never be used post-hoc to excuse a bad
#: draft. faithfulness.py scores recall over the expressible requirements
#: and reports the policy ones separately, as obligations handed to the
#: deployment layer.
POLICY_KIND = "policy"


@dataclass
class Requirement:
    """One atomic, checkable requirement distilled from the intent."""
    rid: str                      # "R1", "R2", ...
    kind: str                     # one of REQUIREMENT_KINDS
    text: str                     # one sentence, plain language
    who: list[str] = field(default_factory=list)   # role names involved
    source: str = "document"      # "document" | "answer" | "assumption"
    priority: str = DEFAULT_PRIORITY              # see PRIORITIES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Requirement":
        kind = d.get("kind", "other")
        if kind not in REQUIREMENT_KINDS:
            kind = "other"
        prio = str(d.get("priority", DEFAULT_PRIORITY)).lower()
        if prio not in PRIORITIES:
            prio = DEFAULT_PRIORITY
        return cls(rid=str(d["rid"]), kind=kind, text=str(d["text"]),
                   who=[str(w) for w in d.get("who", [])],
                   source=str(d.get("source", "document")),
                   priority=prio)


#: What a named entity in the document turns out to be. The test: does the
#: document describe a message crossing INTO or OUT OF it? If yes it is a
#: role — including tool roles (a validator that emits a verdict is a role,
#: not scenery). If no, it is a resource, and its rules are access
#: constraints rather than protocol structure.
ROLE_KINDS = ("agent", "tool", "orchestrator", "user")


@dataclass
class Resource:
    """A named thing that is written or read but never sends or receives.

    Config files, tables, clusters. They fail the role test, so they are
    not participants — but their rules are load-bearing: "two workers must
    not edit this file at once" is mutual exclusion between sessions, which
    no single global type expresses. Recording them separately keeps them
    out of the protocol AND stops them being forgotten.
    """
    name: str
    kind: str = "file"          # file | table | cluster | service | other
    access: str = "read"        # read | shared-write | exclusive-write
    rule: str = ""              # the constraint in plain language

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Resource":
        return cls(name=str(d.get("name", "")).strip(),
                   kind=str(d.get("kind", "file")).strip() or "file",
                   access=str(d.get("access", "read")).strip() or "read",
                   rule=str(d.get("rule", "")).strip())


@dataclass
class SessionInvariant:
    """A counter or budget that must hold for the whole session.

    "At most three repair rounds", "stop after six calls with no artifact".
    These are not orderings — they are stateful properties over the session
    history, checked against a ledger as it evolves. A document full of
    them is a document whose author kept hitting non-termination.
    """
    name: str
    bound: str                  # "<= 3", "<= 6 calls without an artifact"
    resets_on: str = ""         # the event that clears the counter
    on_breach: str = ""         # what must happen when it trips

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionInvariant":
        return cls(name=str(d.get("name", "")).strip(),
                   bound=str(d.get("bound", "")).strip(),
                   resets_on=str(d.get("resets_on", "")).strip(),
                   on_breach=str(d.get("on_breach", "")).strip())


@dataclass
class Goal:
    """An outcome the session exists to achieve, with the observable that
    tells you it happened. Distinct from a requirement: a requirement
    constrains HOW the work proceeds, a goal states WHAT must be true at
    the end. A protocol can satisfy every requirement and still achieve
    nothing — type safety and progress are different properties."""
    gid: str
    text: str
    evidence: str = ""          # how you would know this goal was met
    marker: str = ""            # the interaction id that signals it (I3)
    predicate: str = ""         # what its payload must satisfy
    final: bool = False         # the goal that ends the session

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Goal":
        return cls(gid=str(d.get("gid", "G?")), text=str(d.get("text", "")),
                   evidence=str(d.get("evidence", "")),
                   marker=str(d.get("marker", "")).strip(),
                   predicate=str(d.get("predicate", "")).strip(),
                   final=bool(d.get("final", False)))


@dataclass
class Field:
    """One item of data a handover carries.

    `constraint` is the reason this exists. A protocol that types a payload
    as `string` says nothing about whether the amount exceeds a threshold
    or the justification is non-empty — and "wrong value, right shape" is a
    failure no structural type can catch. These constraints are what
    compile into the refinement-guard sidecar (`.refn`) beside the
    protocol, so the monitor can reject a legal-looking message carrying an
    illegal value.
    """
    name: str
    type: str = "string"        # string | int | bool | double | unit
    constraint: str = ""        # e.g. "greater than 500", "non-empty"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Field":
        return cls(name=str(d.get("name", "")).strip(),
                   type=str(d.get("type", "string")).strip() or "string",
                   constraint=str(d.get("constraint", "")).strip())


#: How many times an interaction may occur. Free text on purpose — real
#: answers are things like "once per pair" or "at most 3 repair rounds",
#: which no small enum captures — but these are the shapes that matter, and
#: an unbounded repeat is the one that turns into a non-terminating session.
CARDINALITY_HINTS = ("exactly once", "at most once", "once per <thing>",
                     "one or more", "at most N times", "unbounded")


@dataclass
class Interaction:
    """One intended exchange, in business terms — who hands what to whom,
    what data it carries, when, and how many times.

    First-class on purpose. Without it the drafter has to invent the entire
    message structure from prose, and the reviewer cannot see the intended
    shape until a protocol exists. With it, the interaction graph is
    drawable the moment interrogation ends, and any message in the drafted
    protocol that matches no declared interaction is visibly invented
    rather than merely "ungrounded" after the fact.
    """
    iid: str
    sender: str
    receiver: str
    what: str                   # the information carried, plain language
    when: str = ""              # trigger / precondition
    optional: bool = False      # only on some branch?
    carries: list[Field] = field(default_factory=list)
    cardinality: str = ""       # see CARDINALITY_HINTS
    #: Interaction ids that must ALL have completed first. A join — the
    #: construct where informal coordination documents deadlock, because
    #: prose says "after both finish" and nobody notices that one branch
    #: can never produce its half. Explicit here so the drafter has to
    #: realize it and a reader can see it.
    waits_for: list[str] = field(default_factory=list)

    def carries_text(self) -> str:
        return ", ".join(
            f"{f.name}: {f.type}" + (f" ({f.constraint})" if f.constraint
                                     else "")
            for f in self.carries)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["carries"] = [f.to_dict() for f in self.carries]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Interaction":
        return cls(iid=str(d.get("iid", "I?")),
                   sender=str(d.get("from") or d.get("sender", "")),
                   receiver=str(d.get("to") or d.get("receiver", "")),
                   what=str(d.get("what", "")), when=str(d.get("when", "")),
                   optional=bool(d.get("optional", False)),
                   carries=[Field.from_dict(f) for f in d.get("carries", [])
                            if str(f.get("name", "")).strip()],
                   cardinality=str(d.get("cardinality", "")).strip(),
                   waits_for=[str(w).strip() for w in d.get("waits_for", [])
                              if str(w).strip()])


@dataclass
class DistilledIntent:
    """The interrogation's structured output — the drafter's actual input."""
    mission: str
    roles: list[dict[str, str]]            # [{"name":..., "description":...}]
    requirements: list[Requirement]
    completion_signal: str
    goals: list[Goal] = field(default_factory=list)
    interactions: list[Interaction] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    invariants: list[SessionInvariant] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def role_names(self) -> list[str]:
        return [r["name"] for r in self.roles]

    def requirements_text(self, kinds: Optional[list[str]] = None) -> str:
        return "\n".join(
            f"- [{r.rid}][{r.kind}] {r.text}"
            + (f" (roles: {', '.join(r.who)})" if r.who else "")
            for r in self.requirements
            if kinds is None or r.kind in kinds)

    #: Kinds that are reported but never graded against the protocol, each
    #: for its own reason: POLICY cannot be expressed by any session type;
    #: INTERIOR is deliberately left untyped inside a role.
    UNGRADED_KINDS = (POLICY_KIND, INTERIOR_KIND)

    def protocol_requirements(self) -> list[Requirement]:
        """Requirements the protocol layer can actually realize — the only
        ones it is honest to score a protocol against."""
        return [r for r in self.requirements
                if r.kind not in self.UNGRADED_KINDS]

    def policy_requirements(self) -> list[Requirement]:
        """Requirements handed to the deployment layer (see POLICY_KIND)."""
        return [r for r in self.requirements if r.kind == POLICY_KIND]

    def must_requirements(self) -> list[Requirement]:
        """The obligations — the verdict turns on these alone.

        A protocol with every obligation covered and a few conveniences
        blurred is sound; one missing an authorization guard is not, however
        high its overall percentage. Scoring both equally is what produced
        "3 of 19" and told the reader nothing about whether the thing was
        safe."""
        return [r for r in self.protocol_requirements()
                if r.priority == "must"]

    def interior_requirements(self) -> list[Requirement]:
        """Intra-role procedure, untyped by design (see INTERIOR_KIND)."""
        return [r for r in self.requirements if r.kind == INTERIOR_KIND]

    def typed_surface_ratio(self) -> float:
        """Fraction of the checklist that is genuinely coordination.

        A low number is a finding about the DOCUMENT, not a failure of the
        drafter: most of a procedure manual is usually intra-role work."""
        n = len(self.requirements)
        return (len(self.protocol_requirements()) / n) if n else 0.0

    def joins(self) -> list["Interaction"]:
        """Interactions gated on more than one predecessor — the deadlock
        candidates."""
        return [i for i in self.interactions if len(i.waits_for) > 1]

    def shared_write_resources(self) -> list["Resource"]:
        """Resources two participants may write — mutual exclusion that no
        single global type can express."""
        return [r for r in self.resources if "write" in r.access]

    def value_constraints(self) -> list[tuple[str, "Field"]]:
        """(interaction id, field) for every payload field carrying a
        constraint — the raw material of the refinement-guard sidecar."""
        return [(i.iid, f) for i in self.interactions for f in i.carries
                if f.constraint]

    def unbounded_repeats(self) -> list["Interaction"]:
        """Interactions declared to repeat without a stated bound.

        Surfaced rather than silently accepted: an unbounded repeat is how
        a session fails to terminate, and the honest moment to notice it is
        while the checklist is still being reviewed."""
        return [i for i in self.interactions
                if "unbounded" in i.cardinality.lower()
                or "one or more" in i.cardinality.lower()]

    def to_markdown(self, include_policy: bool = True) -> str:
        """`include_policy=False` renders the protocol-scoped view — what a
        faithful protocol could possibly encode. That is the fair reference
        for back-translation comparison: a reconstruction derived from the
        protocol alone cannot recover constraints the protocol cannot
        express, so scoring it against them would penalize the drafter for
        a limit of the formalism."""
        lines = ["# Distilled intent", "", "## Mission", self.mission, "",
                 "## Roles"]
        lines += [f"- **{r['name']}**"
                  + (f" ({r['kind']})" if r.get("kind") else "")
                  + f" — {r.get('description', '')}"
                  + (f"\n    MUST NOT: {'; '.join(r['must_not'])}"
                     if r.get("must_not") else "")
                  for r in self.roles]
        if self.resources:
            lines += ["", "## Shared resources (not participants — nothing "
                          "sends or receives here)"]
            lines += [f"- **{r.name}** ({r.kind}, {r.access})"
                      + (f" — {r.rule}" if r.rule else "")
                      for r in self.resources]
        if self.invariants:
            lines += ["", "## Session invariants (must hold across the whole "
                          "run)"]
            lines += [f"- **{v.name}**: {v.bound}"
                      + (f" — resets on {v.resets_on}" if v.resets_on else "")
                      + (f" — on breach: {v.on_breach}" if v.on_breach else "")
                      for v in self.invariants]
        if self.goals:
            lines += ["", "## Goals — what must be true at the end"]
            lines += [f"- [{g.gid}]{' FINAL' if g.final else ''} {g.text}"
                      + (f"\n    signalled by: {g.marker}" if g.marker else "")
                      + (f"\n    payload must satisfy: {g.predicate}"
                         if g.predicate else "")
                      + (f"\n    evidence: {g.evidence}" if g.evidence else "")
                      for g in self.goals]
        if self.interactions:
            lines += ["", "## Intended interactions — who hands what to whom"]
            lines += [f"- [{i.iid}] {i.sender} → {i.receiver}: {i.what}"
                      + (f"\n    carries: {i.carries_text()}"
                         if i.carries else "")
                      + (f"\n    when: {i.when}" if i.when else "")
                      + (f"\n    how often: {i.cardinality}"
                         if i.cardinality else "")
                      + (f"\n    waits for ALL of: {', '.join(i.waits_for)}"
                         if i.waits_for else "")
                      + ("\n    only on some branch" if i.optional else "")
                      for i in self.interactions]
            joins = self.joins()
            if joins:
                lines += ["", "### Joins — every one of these must be "
                              "reachable on every branch, or the session "
                              "deadlocks"]
                lines += [f"- {i.iid} waits for "
                          f"{', '.join(i.waits_for)}" for i in joins]
            guards = self.value_constraints()
            if guards:
                lines += ["", "### Value constraints these payloads must "
                              "satisfy (compile to refinement guards)"]
                lines += [f"- {iid}.{f.name} ({f.type}): {f.constraint}"
                          for iid, f in guards]
        lines += ["", "## Requirements",
                  self.requirements_text(
                      kinds=[k for k in REQUIREMENT_KINDS
                             if k != POLICY_KIND]),
                  "", "## Completion signal", self.completion_signal]
        interior = self.interior_requirements()
        if interior:
            lines += ["", "## Intra-role procedure — untyped interior, NOT "
                          "part of the protocol",
                      "These describe work inside a single role. They are "
                      "real, but no protocol expresses them; do not try to "
                      "encode them as messages."]
            lines += [f"- [{r.rid}] {r.text}" for r in interior]
        if self.non_goals:
            lines += ["", "## Out of scope (do NOT build these)"]
            lines += [f"- {n}" for n in self.non_goals]
        policy = self.policy_requirements() if include_policy else []
        if policy:
            lines += ["", "## Policy requirements (enforced OUTSIDE the "
                          "protocol — not expressible as message ordering)"]
            lines += [f"- [{r.rid}] {r.text}" for r in policy]
        if self.open_questions:
            lines += ["", "## Open questions (explicitly unresolved)"]
            lines += [f"- {q}" for q in self.open_questions]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["requirements"] = [r.to_dict() for r in self.requirements]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DistilledIntent":
        return cls(
            mission=str(d["mission"]),
            roles=[{"name": str(r["name"]),
                    "description": str(r.get("description", ""))}
                   for r in d.get("roles", [])],
            requirements=[Requirement.from_dict(r)
                          for r in d.get("requirements", [])],
            completion_signal=str(d.get("completion_signal", "")),
            open_questions=[str(q) for q in d.get("open_questions", [])],
            provenance=dict(d.get("provenance", {})))


@dataclass
class QA:
    round: int
    question: str
    answer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterrogationResult:
    distilled: DistilledIntent
    transcript: list[QA]
    rounds_used: int
    forced_finish: bool           # True = hit max_rounds, distillation forced
    meter: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"distilled": self.distilled.to_dict(),
                "transcript": [qa.to_dict() for qa in self.transcript],
                "rounds_used": self.rounds_used,
                "forced_finish": self.forced_finish,
                "meter": self.meter}


@dataclass
class CoverageVerdict:
    rid: str
    covered: str                  # "yes" | "partial" | "no"
    evidence: str                 # protocol lines / reasoning cited

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FaithfulnessReport:
    coverage: list[CoverageVerdict]
    recall: float                 # fraction of requirements covered "yes"
    ungrounded: list[str]         # protocol interactions no requirement grounds
    backtranslation: dict[str, Any]   # {"score": 0-100, "reconstructed": str,
                                      #  "missing": [...], "added": [...]}
    gold_equivalent: Optional[bool]   # E5 verdict when a gold protocol exists
    faithful: bool
    rule: str                     # human-readable statement of the verdict rule
    #: How much of the checklist was in scope at all: graded vs policy vs
    #: intra-role interior, plus the typed-surface ratio. Recall alone
    #: invites the wrong conclusion when most of a document is not
    #: coordination.
    scope: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"coverage": [c.to_dict() for c in self.coverage],
                "recall": self.recall, "ungrounded": self.ungrounded,
                "backtranslation": self.backtranslation,
                "gold_equivalent": self.gold_equivalent,
                "faithful": self.faithful, "rule": self.rule,
                "scope": self.scope}


@dataclass
class LoopRecord:
    """One corpus row — everything one loop episode produced."""
    episode_id: str
    intent_sha256: str
    intent_chars: int
    distilled: dict[str, Any]
    transcript: list[dict[str, Any]]
    draft_attempts: list[dict[str, Any]]   # [{"k":1,"valid":bool,"validator_msg":str,"chars":int}]
    final_protocol: Optional[str]          # validated text, or None if never valid
    valid: bool
    faithfulness: Optional[dict[str, Any]]
    meter: dict[str, Any]
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoopRecord":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


# ── JSON extraction (models wrap JSON in prose/fences more often than not) ──

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM reply.

    Tries, in order: fenced ```json blocks, the first balanced {...} span.
    Raises ValueError with the offending text excerpt on failure — callers
    decide whether to retry the LLM call.
    """
    for candidate in _FENCE_RE.findall(text):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError(
        f"no parseable JSON object in LLM reply "
        f"(first 200 chars: {text[:200]!r})")
