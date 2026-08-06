"""mockdata.py — one coherent scripted episode for --mock runs and tests.

A miniature quarterly-report scenario: the document states most of the
requirements, one fact lives ONLY in the stakeholder's head
(HIDDEN_NOTES: the approval threshold), and the scripts walk the loop
through one ask round, a distillation that includes the surfaced fact, a
first draft the (mock) validator rejects, and a successful repair — so
every code path (interrogation, hidden-fact surfacing, rejection, repair,
faithfulness) is exercised offline, deterministically, for free.
"""
from __future__ import annotations

import json

DEMO_DOCUMENT = """We need a quarterly report workflow. A Requester kicks \
things off by asking our Analyst for the quarter's figures. The Analyst \
prepares an analysis and it must be approved before anything goes out — \
approvals are the Approver's job. Once approved, the Analyst sends the \
final report back to the Requester and everyone is done. Company policy \
has an extra review rule for large amounts, ask finance about the details."""

HIDDEN_NOTES = """The extra review rule: analyses covering more than \
$100,000 must carry a written justification note; the Approver rejects \
any large analysis without one. Rejected analyses go back to the Analyst \
for one revision."""

# ── interrogator script: one ask round, then done ───────────────────────
INTERROGATOR_ROUND1 = json.dumps({
    "action": "ask",
    "questions": [
        "1. What is the extra review rule for large amounts the document "
        "mentions?",
        "2. What happens if the Approver rejects an analysis?"]})

INTERROGATOR_DONE = json.dumps({
    "action": "done",
    "distilled": {
        "mission": "Produce an approved quarterly report: the Requester "
                   "asks the Analyst for figures, the analysis is approved "
                   "by the Approver, and the approved report returns to "
                   "the Requester.",
        "roles": [
            {"name": "Requester", "description": "kicks off the request "
             "and receives the final report"},
            {"name": "Analyst", "description": "prepares the analysis and "
             "the final report"},
            {"name": "Approver", "description": "approves or rejects "
             "analyses before release"}],
        "requirements": [
            {"rid": "R1", "kind": "ordering", "who": ["Requester", "Analyst"],
             "text": "The Requester's data request reaches the Analyst "
                     "before any analysis is prepared.",
             "source": "document"},
            {"rid": "R2", "kind": "authorization",
             "who": ["Analyst", "Approver"],
             "text": "Every analysis is approved by the Approver before "
                     "the final report is sent.", "source": "document"},
            {"rid": "R3", "kind": "value", "who": ["Analyst", "Approver"],
             "text": "Analyses over $100,000 must include a written "
                     "justification note or the Approver rejects them.",
             "source": "answer"},
            {"rid": "R4", "kind": "branch", "who": ["Approver", "Analyst"],
             "text": "A rejected analysis goes back to the Analyst for "
                     "one revision.", "source": "answer"},
            {"rid": "R5", "kind": "termination",
             "who": ["Analyst", "Requester"],
             "text": "The session ends when the Requester receives the "
                     "final report.", "source": "document"}],
        "completion_signal": "The Requester holds the approved final "
                             "report.",
        "open_questions": []}})

STAKEHOLDER_ANSWERS_ROUND1 = """1. Analyses covering more than $100,000 \
must carry a written justification note; the Approver rejects any large \
analysis that lacks one.
2. A rejected analysis goes back to the Analyst, who may revise it once \
and resubmit."""

# ── drafter script: first draft invalid (unbalanced brace), repair fixes ─
BROKEN_DRAFT = """global protocol QuarterlyReport(role Requester, role Analyst, role Approver) {
    DataRequest(string) from Requester to Analyst;
    Analysis(string) from Analyst to Approver;
    choice at Approver {
        Approval(string) from Approver to Analyst;
        FinalReport(string) from Analyst to Requester;
    } or {
        Rejection(string) from Approver to Analyst;
        RevisedAnalysis(string) from Analyst to Approver;
        Approval(string) from Approver to Analyst;
        FinalReport(string) from Analyst to Requester;
"""

FIXED_DRAFT = BROKEN_DRAFT + "    }\n}\n"
GUARDED_FIXED_DRAFT = FIXED_DRAFT + """=== REFN ===
Analysis.justification :: amount <= 100000 or justification is non-empty
"""

# ── faithfulness scripts ────────────────────────────────────────────────
COVERAGE_REPLY = json.dumps({
    "verdicts": [
        {"rid": "R1", "covered": "yes",
         "evidence": "DataRequest from Requester to Analyst opens the "
                     "protocol, before Analysis."},
        {"rid": "R2", "covered": "yes",
         "evidence": "Approval from Approver to Analyst precedes "
                     "FinalReport on every branch."},
        {"rid": "R3", "covered": "yes",
         "evidence": "Value guard on Analysis payload; rejection branch "
                     "exists at the Approver."},
        {"rid": "R4", "covered": "yes",
         "evidence": "Rejection branch routes RevisedAnalysis from the "
                     "Analyst exactly once."},
        {"rid": "R5", "covered": "yes",
         "evidence": "FinalReport to Requester terminates both branches."}],
    "ungrounded": []})

BACKTRANSLATION_REPLY = ("A requester asks an analyst for the quarter's "
                         "figures. The analyst prepares an analysis that an "
                         "approver must approve before release; large "
                         "analyses need a justification note or they are "
                         "rejected back to the analyst for one revision. "
                         "The approved final report goes to the requester, "
                         "which ends the work.")

COMPARE_REPLY = json.dumps({"score": 92, "missing": [], "added": []})

INTERROGATOR_SCRIPT = [INTERROGATOR_ROUND1, INTERROGATOR_DONE]
STAKEHOLDER_SCRIPT = [STAKEHOLDER_ANSWERS_ROUND1]
DRAFTER_SCRIPT = [BROKEN_DRAFT, GUARDED_FIXED_DRAFT]
EVAL_SCRIPT = [COVERAGE_REPLY, BACKTRANSLATION_REPLY, COMPARE_REPLY]
