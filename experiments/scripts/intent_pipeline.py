"""intent_pipeline.py — intent authoring + interrogation/distillation front-end.

Produces the intent artifacts under experiments/cases/<case>/intent/ that the
fair intent-carrying policy needs (docs/BENCHMARK_PLAN_V3.md, V3.1 amendment):

  intent.md            document-scale user intent. Two provenances:
                         --from-file  : quoted VERBATIM from the real use
                                        case's own materials (source: git)
                         (no flag)    : LLM-authored stakeholder document
                                        consistent with the case's goals
                                        (source: llm_authored)
  intent_distilled.md  the "interrogation" step's output: what an intake
                       agent would extract by questioning the stakeholder —
                       mission, distilled goals, constraints, completion
                       signal. Grading NEVER uses this text; the canonical
                       goal predicates in case.yaml stay the answer key
                       (answer-key invariance, BENCHMARK_FAIRNESS_REVIEW
                       Problem 2). This is prompt material only.
  role_briefs.yaml     one distilled task brief per role — what a WORKER
                       carries under the fair policy instead of the whole
                       intent document. Shared verbatim by every fair arm,
                       so briefs are held-constant prose, not a per-arm
                       advantage.
  provenance.json      source, sha256s, setup-cost metering, approval flag.

Safety guards (mechanical, no LLM):
  * label-leak guard — neither intent.md nor any brief may contain a message
    label from the canonical protocol or from the LLM-drafted protocols.
    Otherwise the "never saw the vocabulary" arms (the repaired `bare` and
    `maf_groupchat`, post-2026-08-05 consolidation) would be handed the
    answer key through the back door, re-opening fairness Problem 1 in
    reverse.
  * goal-coverage report — canonical goal descriptions side-by-side with the
    distilled goals for HUMAN sign-off (`approve`); the distillation may
    rephrase but must cover every canonical goal.

Setup cost disclosure: every LLM call is counted and its prompt/response
sizes recorded in provenance.json (approx_tokens = chars/4 — the Foundry
utility-agent path does not expose usage numbers). Reports must quote this
as the one-time distillation line item, mirroring the disclosed
protocol-drafting cost.

Two operating modes:

  SYNTHESIZED (the benchmark-campaign default) — `synth` runs the whole
  front-end unattended: author (skipped if intent.md already exists, so a
  git-sourced intent is preserved) -> distill -> automatic LLM coverage
  check -> auto-approve. Provenance records `approved_by: "auto-llm"` so
  every report can disclose that the intent package was synthesized
  end-to-end without a human in the loop. `synth --all` prepares every
  case; run it BEFORE a campaign so no arm ever fail-fasts on a missing
  role_briefs.yaml mid-run.

  HUMAN-GATED — `author` / `distill` / `check` / `approve` are the same
  steps individually, with `approve` recording `approved_by: "human"`
  (which supersedes an earlier auto approval and is never overwritten by
  a later `synth`).

Usage:
  python experiments/scripts/intent_pipeline.py synth   <case_id>|--all [--from-file PATH] [--target-words N] [--max-brief-chars N] [--force]
  python experiments/scripts/intent_pipeline.py author  <case_id> [--from-file PATH] [--target-words N]
  python experiments/scripts/intent_pipeline.py distill <case_id> [--max-brief-chars N]
  python experiments/scripts/intent_pipeline.py check   <case_id>
  python experiments/scripts/intent_pipeline.py approve <case_id>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
STJP_CORE = REPO_ROOT / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml  # noqa: E402

from case_loader import Case  # noqa: E402


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class _MeteredLLM:
    """LLMClient wrapper that counts calls + prompt/response chars.

    The Foundry utility-agent path returns text only (no usage object), so
    metering is by character count with the standard chars/4 approximation —
    disclosed as approximate in provenance.json.
    """

    def __init__(self):
        from stjp_core.foundry.llm_client import LLMClient
        self._client = LLMClient()
        self.calls = 0
        self.prompt_chars = 0
        self.completion_chars = 0

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 4096) -> str:
        self.calls += 1
        self.prompt_chars += len(system_prompt) + len(user_prompt)
        out = self._client.generate(system_prompt, user_prompt,
                                    max_tokens=max_tokens) or ""
        self.completion_chars += len(out)
        return out

    def meter(self) -> dict:
        return {
            "llm_calls": self.calls,
            "prompt_chars": self.prompt_chars,
            "completion_chars": self.completion_chars,
            "approx_tokens": (self.prompt_chars + self.completion_chars) // 4,
            "metering_note": "chars/4 approximation; Foundry utility path "
                             "exposes no usage counts",
        }


def _load_provenance(case: Case) -> dict:
    p = case.intent_dir / "provenance.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_provenance(case: Case, prov: dict) -> None:
    case.intent_dir.mkdir(parents=True, exist_ok=True)
    (case.intent_dir / "provenance.json").write_text(
        json.dumps(prov, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Label-leak guard
# ---------------------------------------------------------------------------

def _protocol_labels(case: Case) -> set[str]:
    """All message labels an arm could be graded against: canonical protocol
    plus any LLM-drafted variants. These words must NOT appear in intent.md
    or in any role brief."""
    from stjp_core.compiler.protocol_parser import parse_protocol_file
    labels: set[str] = set()
    paths = [case.protocol_path]
    for kind in ("valid", "unsafe"):
        p = case.case_dir / "protocols" / "llm_drafts" / kind / "v1.scr"
        if p.exists():
            paths.append(p)
    for path in paths:
        try:
            parsed = parse_protocol_file(path)
            labels.update(m.message_name for m in parsed.messages)
        except Exception as e:
            print(f"  [labels] WARNING: could not parse {path.name}: {e}")
    # Also every goal anchor label (belt-and-suspenders; normally a subset).
    labels.update(g.anchor_label for g in case.goals if g.anchor_label)
    return {l for l in labels if l}


def _find_label_leaks(text: str, labels: set[str]) -> list[str]:
    """Case-sensitive whole-word occurrences of protocol labels in text."""
    leaks = []
    for label in sorted(labels):
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(label)}(?![A-Za-z0-9_])",
                     text):
            leaks.append(label)
    return leaks


# ---------------------------------------------------------------------------
# author — produce intent.md (git-quoted or LLM-authored)
# ---------------------------------------------------------------------------

_AUTHOR_SYSTEM = """You write realistic business requirement documents.
You are given a compact summary of a multi-agent workflow (its purpose, the
team roles, and the outcomes the stakeholder needs). Write the document the
STAKEHOLDER would actually hand over: a briefing/handbook-style requirements
document, in the stakeholder's own voice.

HARD RULES:
- Cover every listed outcome, in prose, so a careful reader could reconstruct
  all of them. Do not omit any.
- Do NOT invent outcomes that contradict the listed ones.
- Do NOT use CamelCase message names, protocol jargon, state machines, or
  anything that looks like a message label or API identifier. Plain business
  language only.
- Realistic texture is welcome (background, policies, formatting
  preferences, non-normative sections) — that is the point: real intents
  bury the requirements inside a longer document.
- Return ONLY the document markdown, no preamble."""


def cmd_author(case_id: str, from_file: str | None,
               target_words: int) -> int:
    case = Case.load(CASES_DIR / case_id)
    case.intent_dir.mkdir(parents=True, exist_ok=True)
    labels = _protocol_labels(case)
    prov = _load_provenance(case)

    if from_file:
        src = Path(from_file)
        if not src.exists():
            print(f"--from-file not found: {src}")
            return 2
        text = src.read_text(encoding="utf-8").strip() + "\n"
        leaks = _find_label_leaks(text, labels)
        if leaks:
            print(f"  WARNING: git-sourced intent contains protocol labels "
                  f"{leaks} — acceptable only if the REAL use case's own "
                  f"text used these words; they will be flagged in "
                  f"provenance.json for the fairness note.")
        (case.intent_dir / "intent.md").write_text(text, encoding="utf-8")
        prov.update({
            "source": "git",
            "source_path": str(src),
            "authored_at": _now(),
            "intent_sha256": _sha(text),
            "intent_chars": len(text),
            "label_leaks_in_source": _find_label_leaks(text, labels),
        })
        _save_provenance(case, prov)
        print(f"  wrote {case.intent_doc_path} ({len(text)} chars, "
              f"source: git verbatim)")
        return 0

    goals_lines = "\n".join(f"  - {g.description}" for g in case.goals)
    roles_lines = "\n".join(f"  - {r}: {case.role_descriptions.get(r, '')}"
                            for r in case.roles)
    user_prompt = f"""Workflow summary (compact — expand into a realistic document):

Purpose:
{case.intent}

Team roles:
{roles_lines}

Required outcomes (cover ALL of these in prose, without protocol jargon):
{goals_lines}

Write the stakeholder's requirements document, about {target_words} words.
"""
    llm = _MeteredLLM()
    text = ""
    for attempt in range(1, 4):
        text = llm.generate(_AUTHOR_SYSTEM, user_prompt,
                            max_tokens=max(2048, target_words * 3)).strip()
        leaks = _find_label_leaks(text, labels)
        if not leaks:
            break
        print(f"  attempt {attempt}: label leak {leaks} — re-drafting")
        user_prompt += (f"\n\nYour previous draft leaked these forbidden "
                        f"identifiers: {leaks}. Rewrite without them.")
    else:
        print(f"  FAILED: could not produce a leak-free intent in 3 attempts")
        return 1

    text += "\n"
    (case.intent_dir / "intent.md").write_text(text, encoding="utf-8")
    import os
    prov.update({
        "source": "llm_authored",
        "author_model": os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        "authored_at": _now(),
        "intent_sha256": _sha(text),
        "intent_chars": len(text),
        "author_meter": llm.meter(),
    })
    _save_provenance(case, prov)
    print(f"  wrote {case.intent_doc_path} ({len(text)} chars, "
          f"source: llm_authored, {llm.calls} LLM calls)")
    return 0


# ---------------------------------------------------------------------------
# distill — interrogation -> intent_distilled.md + role_briefs.yaml
# ---------------------------------------------------------------------------

_DISTILL_SYSTEM = """You are an intake agent for a multi-agent automation team.
A stakeholder handed you a requirements document. Your job is the
interrogation step: identify what the stakeholder actually needs.

Produce a distilled markdown with EXACTLY these sections:
# Mission
(2-3 sentences: what the team must produce, for whom)
# Distilled goals
(a numbered list; each goal one sentence, concrete and checkable — every
requirement in the document that determines success must appear here)
# Constraints and policies
(bullet list of rules the document imposes: thresholds, approvals, orderings)
# Completion signal
(one sentence: how the team knows it is finished)

Plain business language. No CamelCase identifiers, no protocol jargon.
Return ONLY the markdown."""

_BRIEFS_SYSTEM = """You write per-role task briefs for a multi-agent team.
Given the distilled mission/goals/constraints and the team's role list,
write ONE brief per role: what that role must do, what it needs from and
owes to teammates (by ROLE NAME, in plain words), and which constraints
bind it. A worker reading ONLY its brief (not the full document) must be
able to do its part.

HARD RULES:
- Each brief at most {max_chars} characters.
- Plain language. No CamelCase identifiers, no invented message names.
- Return ONLY YAML, of the exact shape:
briefs:
  <RoleName>: |
    <brief>
  <RoleName>: |
    <brief>
Use the exact role names given. No markdown fences."""


def _parse_briefs_yaml(text: str) -> dict[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines()
                         if not l.strip().startswith("```"))
    data = yaml.safe_load(text)
    briefs = data.get("briefs") if isinstance(data, dict) else None
    if not isinstance(briefs, dict):
        raise ValueError("LLM reply is not a `briefs:` YAML mapping")
    return {str(k): str(v).strip() for k, v in briefs.items()}


def cmd_distill(case_id: str, max_brief_chars: int) -> int:
    case = Case.load(CASES_DIR / case_id)
    if not case.intent_doc_path.exists():
        print(f"  no {case.intent_doc_path}; run `author` first (distilling "
              f"the short case.yaml intent instead would be trivial — the "
              f"front-end exists for document-scale intents).")
        return 2
    intent_text = case.intent_doc_path.read_text(encoding="utf-8")
    labels = _protocol_labels(case)
    llm = _MeteredLLM()

    # Pass 1 — interrogation/distillation.
    distilled = llm.generate(
        _DISTILL_SYSTEM,
        f"The stakeholder's document:\n\n{intent_text}",
        max_tokens=2048).strip() + "\n"
    leaks = _find_label_leaks(distilled, labels)
    if leaks:
        print(f"  WARNING: distilled doc leaked labels {leaks}; re-drafting")
        distilled = llm.generate(
            _DISTILL_SYSTEM,
            f"The stakeholder's document:\n\n{intent_text}\n\n"
            f"Do NOT use these identifiers: {leaks}",
            max_tokens=2048).strip() + "\n"

    # Pass 2 — per-role briefs.
    roles_lines = "\n".join(f"  - {r}: {case.role_descriptions.get(r, '')}"
                            for r in case.roles)
    briefs: dict[str, str] = {}
    briefs_sys = _BRIEFS_SYSTEM.replace("{max_chars}", str(max_brief_chars))
    user = (f"Distilled requirements:\n\n{distilled}\n\n"
            f"Team roles:\n{roles_lines}\n")
    for attempt in range(1, 4):
        reply = llm.generate(briefs_sys, user, max_tokens=4096)
        try:
            briefs = _parse_briefs_yaml(reply)
        except Exception as e:
            print(f"  attempt {attempt}: unparseable briefs YAML ({e})")
            continue
        missing = [r for r in case.roles if not briefs.get(r)]
        too_long = [r for r, b in briefs.items()
                    if len(b) > max_brief_chars * 1.2]
        leak_roles = {r: _find_label_leaks(b, labels)
                      for r, b in briefs.items()}
        leak_roles = {r: l for r, l in leak_roles.items() if l}
        if not missing and not too_long and not leak_roles:
            break
        problems = []
        if missing:
            problems.append(f"missing briefs for {missing}")
        if too_long:
            problems.append(f"briefs over {max_brief_chars} chars: {too_long}")
        if leak_roles:
            problems.append(f"forbidden identifiers used: {leak_roles}")
        print(f"  attempt {attempt}: {'; '.join(problems)} — retrying")
        user += f"\n\nFix these problems and return the full YAML again: {problems}"
    else:
        print("  FAILED: could not produce valid role briefs in 3 attempts")
        return 1

    case.intent_dir.mkdir(parents=True, exist_ok=True)
    case.intent_distilled_path.write_text(distilled, encoding="utf-8")
    briefs_yaml = yaml.safe_dump({"briefs": briefs}, sort_keys=False,
                                 allow_unicode=True, width=78)
    (case.intent_dir / "role_briefs.yaml").write_text(briefs_yaml,
                                                      encoding="utf-8")

    prov = _load_provenance(case)
    prov["distill"] = {
        "distilled_at": _now(),
        "distilled_sha256": _sha(distilled),
        "briefs_sha256": _sha(briefs_yaml),
        "max_brief_chars": max_brief_chars,
        "brief_chars": {r: len(b) for r, b in briefs.items()},
        **llm.meter(),
    }
    prov["goals_coverage_approved"] = False   # reset on every re-distill
    _save_provenance(case, prov)

    print(f"  wrote {case.intent_distilled_path.name} "
          f"({len(distilled)} chars) and role_briefs.yaml "
          f"({ {r: len(b) for r, b in briefs.items()} })")
    print(f"  setup cost: {llm.meter()}")
    _print_coverage(case, distilled)
    print("\n  Review the coverage table above, then run:\n"
          f"    python experiments/scripts/intent_pipeline.py approve {case_id}")
    return 0


# ---------------------------------------------------------------------------
# check / approve — goal coverage (human-gated) + guard re-run
# ---------------------------------------------------------------------------

def _print_coverage(case: Case, distilled: str) -> None:
    """Side-by-side: canonical goal descriptions vs the distilled goals
    section. Coverage is judged by a HUMAN (approve) — no fuzzy matching is
    used as evidence, per the plan's no-fuzzy rule. The canonical predicates
    in case.yaml remain the answer key regardless."""
    m = re.search(r"#\s*Distilled goals\s*\n(.*?)(?:\n#|\Z)", distilled,
                  re.DOTALL | re.IGNORECASE)
    distilled_goals = m.group(1).strip() if m else "(section not found!)"
    print("\n  --- goal coverage (human sign-off required) ---")
    print("  canonical goals (case.yaml — the answer key, unchanged):")
    for g in case.goals:
        print(f"    {g.id}: {g.description}")
    print("  distilled goals (prompt material only):")
    for line in distilled_goals.splitlines():
        print(f"    {line}")


def cmd_check(case_id: str) -> int:
    case = Case.load(CASES_DIR / case_id)
    prov = _load_provenance(case)
    labels = _protocol_labels(case)
    ok = True
    for name, path in (("intent.md", case.intent_doc_path),
                       ("intent_distilled.md", case.intent_distilled_path)):
        if not path.exists():
            print(f"  {name}: MISSING")
            ok = False
            continue
        text = path.read_text(encoding="utf-8")
        leaks = _find_label_leaks(text, labels)
        print(f"  {name}: {len(text)} chars, sha {_sha(text)[:12]}…, "
              f"label leaks: {leaks or 'none'}")
        if leaks and prov.get("source") != "git":
            ok = False
    if case.role_briefs:
        for r, b in case.role_briefs.items():
            leaks = _find_label_leaks(b, labels)
            print(f"  brief[{r}]: {len(b)} chars, leaks: {leaks or 'none'}")
            if leaks:
                ok = False
    else:
        print("  role_briefs.yaml: MISSING (fair-intent arms will fail-fast)")
        ok = False
    if case.intent_distilled_path.exists():
        _print_coverage(case,
                        case.intent_distilled_path.read_text(encoding="utf-8"))
    print(f"  goals_coverage_approved: "
          f"{prov.get('goals_coverage_approved', False)} "
          f"(approved_by: {prov.get('approved_by', '—')})")
    return 0 if ok else 1


def cmd_approve(case_id: str) -> int:
    case = Case.load(CASES_DIR / case_id)
    prov = _load_provenance(case)
    if not case.intent_distilled_path.exists():
        print("  nothing to approve: run distill first")
        return 2
    prov["goals_coverage_approved"] = True
    prov["approved_by"] = "human"
    prov["approved_at"] = _now()
    _save_provenance(case, prov)
    print(f"  goal coverage approved for {case_id} by HUMAN "
          f"(recorded in provenance.json)")
    return 0


# ---------------------------------------------------------------------------
# synth — the unattended benchmark-campaign front-end
# ---------------------------------------------------------------------------

_COVERAGE_SYSTEM = """You are auditing a requirements distillation.
You get (a) a list of canonical required outcomes, each with an id, and
(b) the distilled goals section an intake agent produced from the
stakeholder's document. For EACH canonical outcome decide whether the
distilled goals cover it (same requirement in substance; wording may
differ). Be strict: partial or ambiguous coverage is false.

Return ONLY a JSON object mapping each canonical id to true or false,
e.g. {"G1": true, "G2": false}. No prose, no fences."""


def _auto_coverage_check(case: Case, distilled: str,
                         llm: "_MeteredLLM") -> dict[str, bool]:
    """LLM coverage verdict per canonical goal. This substitutes the human
    sign-off in synthesized mode; it is SETUP tooling, never grading
    evidence (the canonical predicates in case.yaml stay the answer key).
    """
    goals_lines = "\n".join(f"  {g.id}: {g.description}" for g in case.goals)
    user = (f"Canonical required outcomes:\n{goals_lines}\n\n"
            f"Distilled goals produced by the intake agent:\n{distilled}\n")
    for attempt in range(2):
        reply = (llm.generate(_COVERAGE_SYSTEM, user, max_tokens=512) or "").strip()
        if reply.startswith("```"):
            reply = "\n".join(l for l in reply.splitlines()
                              if not l.strip().startswith("```"))
        s, e = reply.find("{"), reply.rfind("}")
        try:
            verdicts = json.loads(reply[s:e + 1])
            return {g.id: bool(verdicts.get(g.id, False)) for g in case.goals}
        except Exception:
            continue
    return {g.id: False for g in case.goals}


def cmd_synth(case_id: str, from_file: str | None, target_words: int,
              max_brief_chars: int, force: bool = False) -> int:
    """author (if needed) -> distill -> auto coverage check -> auto-approve.

    Fully unattended: this is the preprocessing stage a benchmark campaign
    runs per case BEFORE any agents start, so that every arm finds a
    complete, already-approved intent package (intent.md +
    intent_distilled.md + role_briefs.yaml + provenance.json) and no arm
    fail-fasts mid-campaign. Approval is recorded as approved_by
    "auto-llm" — the disclosed marker that the package is SYNTHESIZED
    (no human reviewed it). An existing HUMAN approval is never
    overwritten.
    """
    case = Case.load(CASES_DIR / case_id)

    # 1) author — skipped when intent.md exists (preserves git-sourced
    #    intents and keeps synth idempotent), unless --force.
    if force or not case.intent_doc_path.exists():
        rc = cmd_author(case_id, from_file, target_words)
        if rc != 0:
            print(f"  [{case_id}] synth ABORTED at author (rc={rc})")
            return rc
    else:
        print(f"  [{case_id}] intent.md exists "
              f"({case.intent_doc_path.stat().st_size} bytes) — author skipped")

    # 2) distill — skipped when both artifacts exist, unless --force.
    case = Case.load(CASES_DIR / case_id)   # reload (author may have run)
    briefs_path = case.intent_dir / "role_briefs.yaml"
    if force or not (case.intent_distilled_path.exists()
                     and briefs_path.exists()):
        rc = cmd_distill(case_id, max_brief_chars)
        if rc != 0:
            print(f"  [{case_id}] synth ABORTED at distill (rc={rc})")
            return rc
    else:
        print(f"  [{case_id}] distilled artifacts exist — distill skipped")

    # 3) auto coverage check (re-distill once on failure, then fail loud).
    case = Case.load(CASES_DIR / case_id)
    prov = _load_provenance(case)
    if prov.get("approved_by") == "human" and \
            prov.get("goals_coverage_approved"):
        print(f"  [{case_id}] already HUMAN-approved — auto-approve skipped")
        return 0
    llm = _MeteredLLM()
    distilled = case.intent_distilled_path.read_text(encoding="utf-8")
    verdicts = _auto_coverage_check(case, distilled, llm)
    if not all(verdicts.values()):
        missing = [g for g, ok in verdicts.items() if not ok]
        print(f"  [{case_id}] coverage gaps {missing} — re-distilling once")
        rc = cmd_distill(case_id, max_brief_chars)
        if rc != 0:
            return rc
        case = Case.load(CASES_DIR / case_id)
        distilled = case.intent_distilled_path.read_text(encoding="utf-8")
        verdicts = _auto_coverage_check(case, distilled, llm)
        if not all(verdicts.values()):
            missing = [g for g, ok in verdicts.items() if not ok]
            print(f"  [{case_id}] synth FAILED: distilled goals still miss "
                  f"{missing} after one retry — inspect intent_distilled.md "
                  f"(no approval recorded)")
            return 1

    # 4) auto-approve with explicit synthesized provenance.
    prov = _load_provenance(case)
    prov["goals_coverage_approved"] = True
    prov["approved_by"] = "auto-llm"
    prov["approved_at"] = _now()
    prov["auto_coverage"] = {"verdicts": verdicts, **llm.meter()}
    _save_provenance(case, prov)
    print(f"  [{case_id}] synth COMPLETE — auto-approved (approved_by: "
          f"auto-llm; disclose as SYNTHESIZED in reports)")
    return 0


# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("synth", "author", "distill",
                                        "check", "approve"):
        print(__doc__.split("Usage:")[1] if "Usage:" in (__doc__ or "")
              else "usage: intent_pipeline.py "
                   "{synth|author|distill|check|approve} <case_id> [options]")
        return 2
    cmd, case_id = args[0], args[1]
    rest = args[2:]

    from_file = None
    target_words = 1200
    max_brief_chars = 700
    force = "--force" in rest
    if "--from-file" in rest:
        i = rest.index("--from-file")
        from_file = rest[i + 1]
    if "--target-words" in rest:
        i = rest.index("--target-words")
        target_words = int(rest[i + 1])
    if "--max-brief-chars" in rest:
        i = rest.index("--max-brief-chars")
        max_brief_chars = int(rest[i + 1])

    if cmd == "synth":
        if case_id == "--all":
            case_ids = [p.name for p in sorted(CASES_DIR.iterdir())
                        if p.is_dir() and (p / "case.yaml").exists()]
            print(f"synthesizing intent packages for {len(case_ids)} cases: "
                  f"{case_ids}")
            worst = 0
            for cid in case_ids:
                print(f"\n=== synth {cid} ===")
                worst = max(worst, cmd_synth(cid, None, target_words,
                                             max_brief_chars, force))
            return worst
        return cmd_synth(case_id, from_file, target_words,
                         max_brief_chars, force)
    if cmd == "author":
        return cmd_author(case_id, from_file, target_words)
    if cmd == "distill":
        return cmd_distill(case_id, max_brief_chars)
    if cmd == "check":
        return cmd_check(case_id)
    if cmd == "approve":
        return cmd_approve(case_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
