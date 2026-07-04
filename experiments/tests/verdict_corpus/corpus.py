"""Verdict corpus — 40 traces with known-correct verdicts (BENCHMARK_PLAN_V2 §9).

Tests the TESTERS: before trusting any experiment that uses the monitor or the
severity grader, prove those two instruments give the right verdict on traces
whose answer we already know by hand.

Two instrument groups (24 + 16 = 40 cases):

  MONITOR group  — stjp_core.monitor.SessionMonitor over a projected EFSM.
                   Each case fixes a protocol + trace and asserts the EXACT
                   multiset of violation types (or conformance). Covers: clean
                   linear/branching, off-protocol, wrong-peer, premature
                   termination, refinement failure, ASYNC commuting on
                   independent channels, and value-dependent choice guards
                   (wrong branch = violation; guard-not-evaluable = SILENT).

  GRADER group   — experiments/scripts/severity_grader.AttemptGrader over a
                   finance-shaped severity spec. Asserts the S-class buckets
                   (S0 benign / S1 waste / S2 obligation / S3 progress /
                   S4 disaster), including the documented payload-blind
                   `Approval(False)` milestone case.

Run: python experiments/tests/verdict_corpus/run_verdict_corpus.py
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Protocols used by the MONITOR group (kept tiny; projected once, cached)
# ─────────────────────────────────────────────────────────────────────────────

P_LINEAR = """module vc_linear;
data <java> "java.lang.Double" from "rt.jar" as Double;
data <java> "java.lang.String" from "rt.jar" as String;
global protocol Pipe(role A, role B, role C) {
    M1(Double) from A to B;
    M2(String) from B to C;
    M3(String) from C to A;
}
"""

# M1 payload must be positive — used for the refinement-failure case.
P_LINEAR_REFN = """[A -> B : M1]
type: float
require: x > 0
"""

# Chooser observes Raw first, then branches; guard is keyed on the Raw value.
P_CHOICE = """module vc_choice;
data <java> "java.lang.Double" from "rt.jar" as Double;
data <java> "java.lang.String" from "rt.jar" as String;
global protocol Ch(role Src, role Boss, role X, role Y) {
    Raw(Double) from Src to Boss;
    choice at Boss {
        High(Double) from Boss to X;
        HighNote(String) from Boss to Y;
    } or {
        Low(Double) from Boss to X;
        LowNote(String) from Boss to Y;
    }
    Result(String) from X to Boss;
    Done(String) from Y to Boss;
}
"""

# Boss must take High iff the Raw figure it received is > 50000.
P_CHOICE_REFN = """[choice at Boss]
when: float(Raw) > 50000
require: High
over: Low
"""

# Two independent request/response channels (A<->B and C<->D). Actions on
# different channels commute — the monitor must accept out-of-order arrival.
P_CONC = """module vc_conc;
data <java> "java.lang.String" from "rt.jar" as String;
global protocol Conc(role A, role B, role C, role D) {
    P(String) from A to B;
    Q(String) from C to D;
    R(String) from B to A;
    S(String) from D to C;
}
"""


def _ev(sender, receiver, label, payload=""):
    return {"sender": sender, "receiver": receiver, "label": label, "payload": payload}


# Convenience full clean traces (reused as prefixes)
_CH_HIGH = [_ev("Src", "Boss", "Raw", "60000"), _ev("Boss", "X", "High", "60000"),
            _ev("Boss", "Y", "HighNote", "hi"), _ev("X", "Boss", "Result", "r"),
            _ev("Y", "Boss", "Done", "d")]
_CH_LOW = [_ev("Src", "Boss", "Raw", "10"), _ev("Boss", "X", "Low", "10"),
           _ev("Boss", "Y", "LowNote", "lo"), _ev("X", "Boss", "Result", "r"),
           _ev("Y", "Boss", "Done", "d")]
_LIN = [_ev("A", "B", "M1", "5.0"), _ev("B", "C", "M2", "ok"),
        _ev("C", "A", "M3", "done")]


# ─────────────────────────────────────────────────────────────────────────────
# MONITOR cases. expect_types = sorted multiset of ViolationType.value strings
# across ALL roles. Traces are COMPLETE (one injected fault) unless the fault is
# itself a partial run, in which case prematures are enumerated.
# ─────────────────────────────────────────────────────────────────────────────

MONITOR_CASES = [
    dict(id="M01_linear_clean", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"], trace=list(_LIN),
         expect_conformant=True, expect_types=[]),

    dict(id="M02_off_protocol_first_label", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         # A sends a bogus first label; B and C then never get valid input ->
         # A off_protocol, plus A/B/C premature at close.
         trace=[_ev("A", "B", "WrongLabel", "5.0")],
         expect_conformant=False,
         expect_types=["off_protocol", "premature_termination"]),

    dict(id="M03_off_protocol_midway", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         trace=[_ev("A", "B", "M1", "5.0"), _ev("B", "C", "Nope", "x")],
         expect_conformant=False,
         # both endpoints flag Nope (B send-side, C recv-side) + prematures.
         expect_types=["off_protocol", "premature_termination"]),

    dict(id="M04_unexpected_peer", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         trace=[_ev("A", "C", "M1", "5.0")],
         expect_conformant=False,
         # A sends M1 to C (wrong peer). A's own send transition targets B, so
         # from A's view this is off_protocol (label M1 exists but peer C wrong
         # -> unexpected_peer for A). B and C stay premature.
         expect_types=["off_protocol", "premature_termination",
                       "unexpected_peer"]),

    dict(id="M05_premature_termination", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         trace=[_ev("A", "B", "M1", "5.0"), _ev("B", "C", "M2", "ok")],
         expect_conformant=False,
         # A waiting for M3, C owes M3 -> both premature. B done.
         expect_types=["premature_termination", "premature_termination"]),

    dict(id="M06_refinement_fail", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"], refn=P_LINEAR_REFN,
         trace=[_ev("A", "B", "M1", "-3.0")],
         expect_conformant=False, expect_types=["refinement_failed",
                                                "premature_termination"]),

    dict(id="M07_refinement_pass", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"], refn=P_LINEAR_REFN,
         trace=[_ev("A", "B", "M1", "42.0"), _ev("B", "C", "M2", "ok"),
                _ev("C", "A", "M3", "done")],
         expect_conformant=True, expect_types=[]),

    dict(id="M08_choice_high_clean", protocol=P_CHOICE, protocol_name="Ch",
         roles=["Src", "Boss", "X", "Y"], trace=list(_CH_HIGH),
         expect_conformant=True, expect_types=[]),

    dict(id="M09_choice_low_clean", protocol=P_CHOICE, protocol_name="Ch",
         roles=["Src", "Boss", "X", "Y"], trace=list(_CH_LOW),
         expect_conformant=True, expect_types=[]),

    dict(id="M10_choice_result_early_commutes", protocol=P_CHOICE,
         protocol_name="Ch", roles=["Src", "Boss", "X", "Y"],
         # X's send-to-Boss (Result) and its receive-from-Boss (High/Low) are on
         # DIFFERENT channels (different direction), so async subtyping lets the
         # monitor commute past the pending receive and accept Result early —
         # X does NOT flag off-protocol; the run just ends incomplete (prematures).
         trace=[_ev("X", "Boss", "Result", "r")],
         expect_conformant=False,
         expect_types=["premature_termination"]),

    dict(id="M11_choice_guard_wrong_branch", protocol=P_CHOICE,
         protocol_name="Ch", roles=["Src", "Boss", "X", "Y"], refn=P_CHOICE_REFN,
         # Raw=60000 (guard TRUE) but Boss took Low -> choice_guard_violation.
         # The Low branch is otherwise protocol-legal, so no off_protocol.
         trace=[_ev("Src", "Boss", "Raw", "60000"), _ev("Boss", "X", "Low", "60000"),
                _ev("Boss", "Y", "LowNote", "lo"), _ev("X", "Boss", "Result", "r"),
                _ev("Y", "Boss", "Done", "d")],
         expect_conformant=False, expect_types=["choice_guard_violation"]),

    dict(id="M12_choice_guard_high_correct", protocol=P_CHOICE,
         protocol_name="Ch", roles=["Src", "Boss", "X", "Y"], refn=P_CHOICE_REFN,
         # Raw=60000 (guard TRUE) and Boss took High -> conformant.
         trace=list(_CH_HIGH), expect_conformant=True, expect_types=[]),

    dict(id="M13_choice_guard_low_correct", protocol=P_CHOICE,
         protocol_name="Ch", roles=["Src", "Boss", "X", "Y"], refn=P_CHOICE_REFN,
         # Raw=10 (guard FALSE) and Boss took Low -> conformant (guard silent OK).
         trace=list(_CH_LOW), expect_conformant=True, expect_types=[]),

    dict(id="M14_conc_in_order", protocol=P_CONC, protocol_name="Conc",
         roles=["A", "B", "C", "D"],
         trace=[_ev("A", "B", "P", "1"), _ev("C", "D", "Q", "2"),
                _ev("B", "A", "R", "3"), _ev("D", "C", "S", "4")],
         expect_conformant=True, expect_types=[]),

    dict(id="M15_conc_reordered", protocol=P_CONC, protocol_name="Conc",
         roles=["A", "B", "C", "D"],
         # second channel interleaved first — commutes, must be accepted.
         trace=[_ev("C", "D", "Q", "2"), _ev("A", "B", "P", "1"),
                _ev("D", "C", "S", "4"), _ev("B", "A", "R", "3")],
         expect_conformant=True, expect_types=[]),

    dict(id="M16_conc_channel_grouped", protocol=P_CONC, protocol_name="Conc",
         roles=["A", "B", "C", "D"],
         # whole 2nd channel before the 1st — commutes.
         trace=[_ev("C", "D", "Q", "2"), _ev("D", "C", "S", "4"),
                _ev("A", "B", "P", "1"), _ev("B", "A", "R", "3")],
         expect_conformant=True, expect_types=[]),

    dict(id="M17_conc_recv_send_commute", protocol=P_CONC,
         protocol_name="Conc", roles=["A", "B", "C", "D"],
         # B's receive-from-A (P) and send-to-A (R) are DIFFERENT channels
         # (a channel is peer AND direction), so B may emit R before consuming P
         # under async subtyping — accepted, run ends incomplete (prematures).
         trace=[_ev("B", "A", "R", "3")],
         expect_conformant=False,
         expect_types=["premature_termination"]),

    dict(id="M18_extra_after_terminal", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         trace=_LIN + [_ev("A", "B", "M1", "5.0")],
         expect_conformant=False, expect_types=["off_protocol"]),

    dict(id="M19_choice_missing_note", protocol=P_CHOICE, protocol_name="Ch",
         roles=["Src", "Boss", "X", "Y"],
         # High branch but Boss never notifies Y -> Y premature; Boss owes Done-recv.
         trace=[_ev("Src", "Boss", "Raw", "60000"), _ev("Boss", "X", "High", "60000"),
                _ev("X", "Boss", "Result", "r")],
         expect_conformant=False,
         expect_types=["premature_termination", "premature_termination"]),

    dict(id="M20_irrelevant_event_ignored", protocol=P_LINEAR,
         protocol_name="Pipe", roles=["A", "B", "C"],
         trace=[_ev("A", "B", "M1", "5.0"), _ev("Z", "Q", "Noise", "x"),
                _ev("B", "C", "M2", "ok"), _ev("C", "A", "M3", "done")],
         expect_conformant=True, expect_types=[]),

    dict(id="M21_label_type_suffix_ok", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"],
         trace=[_ev("A", "B", "M1(Double)", "5.0"), _ev("B", "C", "M2(String)", "ok"),
                _ev("C", "A", "M3", "done")],
         expect_conformant=True, expect_types=[]),

    dict(id="M22_empty_trace", protocol=P_LINEAR, protocol_name="Pipe",
         roles=["A", "B", "C"], trace=[],
         expect_conformant=False,
         expect_types=["premature_termination", "premature_termination",
                       "premature_termination"]),

    dict(id="M23_conc_wrong_peer", protocol=P_CONC, protocol_name="Conc",
         roles=["A", "B", "C", "D"],
         trace=[_ev("A", "D", "P", "1")],
         expect_conformant=False,
         # A sends P to D -> unexpected_peer (A); D recv-side off_protocol; prematures.
         expect_types=["off_protocol", "premature_termination",
                       "unexpected_peer"]),

    dict(id="M24_wrong_sender_for_shared", protocol=P_CHOICE,
         protocol_name="Ch", roles=["Src", "Boss", "X", "Y"],
         # Y sends Result (should be X). Y off_protocol; X premature (owes Result),
         # Boss premature (owes Result-recv + Done-recv).
         trace=[_ev("Src", "Boss", "Raw", "10"), _ev("Boss", "X", "Low", "10"),
                _ev("Boss", "Y", "LowNote", "lo"), _ev("Y", "Boss", "Result", "r")],
         expect_conformant=False,
         expect_types=["off_protocol", "premature_termination",
                       "unexpected_peer"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# GRADER cases — finance-shaped severity spec, embedded so the corpus is
# self-contained (mirrors experiments/cases/finance/protocols/severity.yaml).
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_SPEC = {
    "milestones": [
        {"id": "revenue_to_audit", "match": "HighRevenue|RequestAudit", "branches": ["high"]},
        {"id": "audit_done", "match": "Audited|AuditComplete", "branches": ["high"]},
        {"id": "approval", "match": "Approval|Approved"},
        {"id": "revenue_analysis", "match": "RevenueAnalysis"},
        {"id": "report", "match": "GenerateReport"},
    ],
    "chains": {
        "high": ["revenue_to_audit", "audit_done", "approval", "revenue_analysis", "report"],
        "standard": ["approval", "revenue_analysis", "report"],
    },
    "terminal": "report",
    "irreversible": [
        {"id": "report", "requires": ["approval"], "requires_high": ["audit_done"]},
    ],
}


def _g(sender, receiver, label):
    return {"lbl": label, "from": sender, "to": receiver}


# Each grader case: branch + events + expected S-class buckets (exact counts).
GRADER_CASES = [
    dict(id="G01_high_clean", branch="high",
         events=[_g("F", "T", "HighRevenue"), _g("T", "R", "Audited"),
                 _g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G02_standard_clean", branch="standard",
         events=[_g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G03_duplicate_milestone_S1", branch="standard",
         events=[_g("V", "R", "Approval"), _g("V", "R", "Approval"),
                 _g("R", "W", "RevenueAnalysis"), _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 1, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G04_benign_extra_S0", branch="standard",
         events=[_g("V", "R", "Approval"), _g("R", "R", "Chitchat"),
                 _g("R", "W", "RevenueAnalysis"), _g("W", "F", "GenerateReport")],
         expect={"S0": 1, "S1": 0, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G05_analysis_before_approval_S2", branch="standard",
         # revenue_analysis before predecessor approval -> S2. Then approval on
         # path; report needs approval (satisfied by feed time) -> S4=0.
         events=[_g("R", "W", "RevenueAnalysis"), _g("V", "R", "Approval"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 1, "S3": 0, "S4": 0}),

    dict(id="G06_no_terminal_S3", branch="standard",
         events=[_g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 1, "S4": 0}),

    dict(id="G07_report_before_approval_S4", branch="standard",
         events=[_g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 1}),

    dict(id="G08_high_report_before_audit_S4", branch="high",
         # report requires approval AND audit_done; audit_done missing -> S4.
         # revenue_analysis fires before audit_done predecessor -> S2.
         events=[_g("F", "T", "HighRevenue"), _g("V", "R", "Approval"),
                 _g("R", "W", "RevenueAnalysis"), _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 2, "S3": 0, "S4": 1}),

    dict(id="G09_repeated_analysis_S1", branch="standard",
         events=[_g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis"),
                 _g("R", "W", "RevenueAnalysis"), _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 1, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G10_high_full_ok_aliases", branch="high",
         events=[_g("F", "T", "RequestAudit"), _g("T", "R", "AuditComplete"),
                 _g("V", "R", "Approved"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0}),

    dict(id="G11_approval_false_payload_blind", branch="standard",
         # DOCUMENTED LIMITATION: grader aligns on LABEL not payload, so an
         # Approval whose payload means "No" still satisfies the milestone.
         # Expected encodes the grader's ACTUAL (payload-blind) verdict; a future
         # payload-aware fix will trip this case and force a conscious update.
         events=[_g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0},
         note="payload-blind: Approval(False) still satisfies the milestone"),

    dict(id="G12_high_audit_before_revenue_S2", branch="high",
         events=[_g("T", "R", "Audited"), _g("F", "T", "HighRevenue"),
                 _g("V", "R", "Approval"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 1, "S3": 0, "S4": 0}),

    dict(id="G13_empty_attempt_S3", branch="standard", events=[],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 1, "S4": 0}),

    dict(id="G14_only_benign_S0_S3", branch="standard",
         events=[_g("R", "R", "Hello"), _g("R", "R", "World")],
         expect={"S0": 2, "S1": 0, "S2": 0, "S3": 1, "S4": 0}),

    dict(id="G15_high_missing_approval_S2_S4", branch="high",
         # audit_done present, approval absent; revenue_analysis before approval
         # predecessor -> S2; report needs approval -> S4.
         events=[_g("F", "T", "HighRevenue"), _g("T", "R", "Audited"),
                 _g("R", "W", "RevenueAnalysis"), _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 1, "S3": 0, "S4": 1}),

    dict(id="G16_standard_full_ok", branch="standard",
         events=[_g("V", "R", "Approved"), _g("R", "W", "RevenueAnalysis"),
                 _g("W", "F", "GenerateReport")],
         expect={"S0": 0, "S1": 0, "S2": 0, "S3": 0, "S4": 0}),
]

assert len(MONITOR_CASES) == 24, len(MONITOR_CASES)
assert len(GRADER_CASES) == 16, len(GRADER_CASES)
TOTAL = len(MONITOR_CASES) + len(GRADER_CASES)
