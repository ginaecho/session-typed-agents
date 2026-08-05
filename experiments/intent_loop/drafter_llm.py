"""drafter_llm.py — a live-LLM Drafter for the t0 interface.

experiments/seam_bench/t0/drafter.py defines the pluggable Drafter ABC but
(by its own transport constraint) ships only MockDrafter and FileDrafter.
This module supplies the missing live implementation on the repo's
Foundry-first ChatLLM seam, so the EXISTING production loop
(t0/repair_loop.run_repair_chain — draft -> real Scribble validate -> on
reject repair with the validator's counterexample, <= 3 rounds) runs
unchanged against a real model. Nothing about the loop is reimplemented
here; only `draft()` / `repair()` are.

Prompt-level tuning (the no-weight-update alternative to SFT) enters
exactly here, as two inputs mined from the loop's own corpus by
optimize.py:

  exemplars   (intent, protocol) few-shot pairs — passed per-call by the
      caller (BM25-retrieved, t0/exemplars.py), folded into the prompt.
  rulebook    short "the validator rejects X, do Y" lesson lines harvested
      from past validator counterexamples — the textual analogue of
      gradient steps: each real failure family becomes one standing
      instruction.

Both are data, not code: swapping a prompt pack changes drafting behavior
with zero training cost, and the corpus keeps enough to compare packs.
"""
from __future__ import annotations

from typing import Optional, Sequence

from experiments.intent_loop.llm import ChatLLM, approx_tokens
from experiments.seam_bench.t0.drafter import (Drafter, UsageInfo,
                                               GUARD_SIDECAR_SENTINEL)

# Kept deliberately small: a syntax reminder, not a tutorial. The validator
# is the authority; the primer only reduces round-1 syntax rejections.
SCRIBBLE_PRIMER = """Scribble global protocol syntax reminder. Start EVERY
protocol with exactly this preamble — the real validator rejects a file
without the module line, and rejects any payload sort that was not declared
("Cannot disambiguate name: string"):

  module Example;

  data <java> "java.lang.String" from "rt.jar" as String;
  data <java> "java.lang.Integer" from "rt.jar" as Int;
  data <java> "java.lang.Boolean" from "rt.jar" as Bool;
  data <java> "java.lang.Double" from "rt.jar" as Double;

  global protocol Name(role A, role B, role C) {
      Label1(string) from A to B;          // message: Label(payload sort)
      choice at B {                        // decision made by B
          Label2(int) from B to C;
          ...
      } or {
          Label3(bool) from B to C;
          ...
      }
      rec LOOP {                           // guarded loop
          Label4(string) from C to A;
          continue LOOP;
      }
  }
Payload sorts are the CAPITALISED names declared above — String, Int, Bool,
Double — one per message, written `Label(String)`, never `Label(string)`,
never `Label(Int,String)`, never a sort you did not declare. Every branch of a
choice must inform any role whose later behavior depends on the decision
(otherwise projection rejects the protocol). Every role declared must
appear in at least one message. A role never sends to itself — work inside
one role is not an interaction. Every `rec` loop must have at least one
branch that does NOT `continue`, or the session can never end."""

_DRAFT_SYSTEM = """You translate a distilled task specification into ONE \
Scribble global protocol.

{primer}

Hard rules:
- Output ONLY the protocol text. No prose, no markdown fences.
- Realize EVERY requirement in the checklist: orderings as message order, \
authorizations as an approval message BEFORE the act it authorizes, \
branches as `choice at <deciding role>`, termination as a final message \
that reaches whoever the completion signal names.
- If the specification lists INTENDED INTERACTIONS, each one becomes a \
message: same sender, same receiver, a label naming what it carries. Add no \
message that no interaction or requirement calls for.
- Honour the declared CARDINALITY. "exactly once" is a plain message; \
"at most once" belongs in a choice branch; a bounded repeat ("at most 3 \
times") is a `rec` loop whose exit branch is reachable at every iteration. \
Never write a loop that cannot terminate.
{guards_block}{rulebook_block}{exemplars_block}"""

_GUARDS_BLOCK = """- The specification lists VALUE CONSTRAINTS. Structural \
types cannot express them, so emit a refinement-guard sidecar after the \
protocol: a line containing exactly `{sentinel}`, then one guard per line \
in the form

    <MessageLabel>.<field> :: <predicate over the value>

covering every listed constraint. Example: `HighRevenue.amount :: amount > \
50000`. The protocol above the sentinel must remain valid Scribble on its \
own.
"""

_REPAIR_SYSTEM = """You repair a Scribble global protocol that the real \
Scribble validator rejected. You will be given the task specification, the \
broken protocol, and the validator's verbatim error output. Fix the error \
while preserving the intended interaction. Output ONLY the corrected \
protocol text, no prose, no fences.

{primer}
{rulebook_block}"""


def _rulebook_block(rulebook: Sequence[str]) -> str:
    if not rulebook:
        return ""
    lines = "\n".join(f"- {r}" for r in rulebook)
    return ("\n\nLessons from previously rejected drafts "
            f"(follow them):\n{lines}\n")


def _exemplars_block(exemplars: Optional[Sequence[tuple[str, str]]]) -> str:
    if not exemplars:
        return ""
    parts = ["\n\nWorked examples (specification -> protocol):"]
    for i, (intent, protocol) in enumerate(exemplars, start=1):
        parts.append(f"\n--- Example {i} specification ---\n{intent}\n"
                     f"--- Example {i} protocol ---\n{protocol}")
    return "\n".join(parts) + "\n"


def strip_fences(text: str) -> str:
    """Models add ``` fences despite instructions; drop them, keep content."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


class ChatDrafter(Drafter):
    """Live Drafter over the ChatLLM seam. k candidates = k independent
    calls (the Foundry utility path exposes no temperature control, so
    diversity comes from sampling alone). Usage is chars/4-approximate at
    $0, surfaced through `usage_for` so t0's estimate_usage reports it as
    measured-approximate rather than a bare word count."""

    def __init__(self, llm: ChatLLM, *,
                 rulebook: Sequence[str] = (),
                 model_label: str = "chat-drafter"):
        self.llm = llm
        self.rulebook = list(rulebook)
        self.model_label = model_label
        self._usage: dict[str, UsageInfo] = {}

    def _record_usage(self, prompt: str, reply: str) -> None:
        self._usage[reply] = UsageInfo(
            tokens_in=approx_tokens(prompt), tokens_out=approx_tokens(reply),
            usd=0.0, model=f"{self.model_label} (chars/4 approx)")

    def draft(self, intent: str, k: int,
              exemplars: Optional[Sequence[tuple[str, str]]] = None
              ) -> list[str]:
        # Ask for guards only when the spec actually carries value
        # constraints — an unconditional instruction invites invented
        # guards, which are worse than none: they enforce a rule nobody
        # agreed to.
        guards = (_GUARDS_BLOCK.format(sentinel=GUARD_SIDECAR_SENTINEL)
                  if "compile to refinement guards" in intent else "")
        system = _DRAFT_SYSTEM.format(
            primer=SCRIBBLE_PRIMER, guards_block=guards,
            rulebook_block=_rulebook_block(self.rulebook),
            exemplars_block=_exemplars_block(exemplars))
        user = f"=== TASK SPECIFICATION ===\n{intent}\n\nWrite the protocol."
        out = []
        for _ in range(k):
            reply = strip_fences(self.llm.complete(system, user,
                                                   stage="draft"))
            self._record_usage(system + user, reply)
            out.append(reply)
        return out

    def repair(self, intent: str, broken: str, counterexample: str) -> str:
        system = _REPAIR_SYSTEM.format(
            primer=SCRIBBLE_PRIMER,
            rulebook_block=_rulebook_block(self.rulebook)
            + (f"\n- The broken draft carries a `{GUARD_SIDECAR_SENTINEL}` "
               f"guard sidecar; keep it, and keep it consistent with the "
               f"labels you end up using.\n"
               if GUARD_SIDECAR_SENTINEL in broken else ""))
        user = (f"=== TASK SPECIFICATION ===\n{intent}\n\n"
                f"=== BROKEN PROTOCOL ===\n{broken}\n\n"
                f"=== VALIDATOR ERROR (verbatim) ===\n{counterexample}\n\n"
                f"Output the corrected protocol.")
        reply = strip_fences(self.llm.complete(system, user, stage="repair"))
        self._record_usage(system + user, reply)
        return reply

    def usage_for(self, text: str) -> Optional[UsageInfo]:
        return self._usage.get(text)
