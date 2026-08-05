"""stakeholder.py — the stakeholder simulator the interrogator questions.

Models the person who WROTE the intent document. Two knobs decide what it
may say, and both exist for benchmark honesty:

  hidden_notes   extra facts the document does NOT contain (requirements
      "buried in the stakeholder's head"). This is what makes multi-turn
      interrogation measurably better than one-shot distillation: a
      distiller that only reads the document can never recover these; an
      interrogator that asks the right question can. Training episodes can
      plant hidden notes and check whether the distilled requirements
      surfaced them.
  improvise      False (default): questions neither the document nor the
      hidden notes answer get the literal reply "NOT SPECIFIED." — the
      interrogator must then record an explicit assumption or open
      question instead of silently inventing an answer. True: the
      simulator may invent a consistent answer but must prefix it with
      "(assumption)". Default False keeps episodes reproducible and keeps
      hallucinated requirements out of the training corpus.
"""
from __future__ import annotations

from typing import Optional

from experiments.intent_loop.llm import ChatLLM

NOT_SPECIFIED = "NOT SPECIFIED."

_SYSTEM_TEMPLATE = """You are the STAKEHOLDER who commissioned a multi-agent \
system. An intake analyst is interviewing you to pin down exactly what you \
need. Answer their questions faithfully.

Ground rules:
- Answer ONLY from your intent document{hidden_clause} below. Quote or \
paraphrase it; do not contradict it.
- If a question is not answered by that material, reply exactly: \
"{not_specified}"{improvise_clause}
- Be concise: a short paragraph per question, no pleasantries.
- Number your answers to match the analyst's question numbers.

=== YOUR INTENT DOCUMENT ===
{document}
{hidden_block}"""

_HIDDEN_BLOCK_TEMPLATE = """
=== ADDITIONAL FACTS YOU KNOW (not written in the document — share them \
only when a question asks about them) ===
{hidden_notes}"""

_IMPROVISE_CLAUSE = (" — unless you can give a reasonable answer consistent "
                     "with the document, in which case prefix it with "
                     "\"(assumption)\".")


class StakeholderSim:
    """Answers interrogator question batches, keeping full dialogue history
    so later answers stay consistent with earlier ones."""

    def __init__(self, llm: ChatLLM, document: str,
                 hidden_notes: Optional[str] = None,
                 improvise: bool = False):
        self.llm = llm
        self.document = document
        self.hidden_notes = hidden_notes
        self.improvise = improvise
        self._history: list[dict[str, str]] = []
        self._system = _SYSTEM_TEMPLATE.format(
            document=document,
            not_specified=NOT_SPECIFIED,
            hidden_clause=(" and the additional facts" if hidden_notes else ""),
            hidden_block=(_HIDDEN_BLOCK_TEMPLATE.format(hidden_notes=hidden_notes)
                          if hidden_notes else ""),
            improvise_clause=(_IMPROVISE_CLAUSE if improvise else ""))

    def answer(self, questions: str) -> str:
        """One interrogation round: a numbered question batch in, the
        stakeholder's numbered answers out."""
        self._history.append({"role": "user", "content": questions})
        reply = self.llm.complete_with_history(
            self._system, self._history, stage="stakeholder")
        self._history.append({"role": "assistant", "content": reply})
        return reply
