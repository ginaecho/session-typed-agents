"""
Goal Elicitor

Takes user intent (natural language) and produces math-checkable goals
anchored to protocol messages. Goals become refinement predicates that
can be verified post-execution by the runtime monitor.

Flow:
  1. User provides intent (NL description of what they want)
  2. LLM extracts structured goals: metric, predicate, anchor message, threshold
  3. Goals are validated for consistency (no contradictions)
  4. Goals are converted to .refn predicates anchored to protocol messages
  5. Post-execution: monitor checks trace against anchored predicates

Can run in mock mode (no LLM needed) for testing.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from stjp_core.compiler.protocol_parser import ParsedProtocol, ProtocolMessage


@dataclass
class Goal:
    """A single math-checkable goal extracted from user intent."""
    id: str                          # e.g. "G1"
    description: str                 # NL description
    metric: str                      # what to measure e.g. "revenue_amount"
    predicate: str                   # Python expression over x e.g. "x > 50000"
    anchor_sender: str               # role that sends the anchored message
    anchor_receiver: str             # role that receives it
    anchor_label: str                # message label to anchor this goal to
    threshold: str = ""              # human-readable threshold e.g. "> 50000"
    verification: str = "runtime"    # "static" or "runtime"
    branch: str = ""                 # if set, goal applies only to trials on
                                     # this branch hint; vacuous (pass) on others


@dataclass
class GoalSet:
    """Collection of goals extracted from a single intent."""
    intent: str
    goals: list[Goal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_refn_text(self) -> str:
        """Convert goals to .refn format for the monitor."""
        lines = [f"# Goals extracted from intent: {self.intent[:80]}"]
        for g in self.goals:
            lines.append(f"\n[{g.anchor_sender} -> {g.anchor_receiver} : {g.anchor_label}]")
            lines.append(f"# Goal {g.id}: {g.description}")
            # Infer type from predicate
            if any(op in g.predicate for op in ['>', '<', '>=', '<=']) and 'len(' not in g.predicate:
                lines.append("type: float")
            elif 'len(' in g.predicate:
                lines.append("type: str")
            lines.append(f"require: {g.predicate}")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            "intent": self.intent,
            "goals": [
                {
                    "id": g.id,
                    "description": g.description,
                    "metric": g.metric,
                    "predicate": g.predicate,
                    "anchor_sender": g.anchor_sender,
                    "anchor_receiver": g.anchor_receiver,
                    "anchor_label": g.anchor_label,
                    "threshold": g.threshold,
                    "verification": g.verification,
                    "branch": g.branch,
                }
                for g in self.goals
            ],
            "warnings": self.warnings,
        }, indent=2)


GOAL_ELICITATION_SYSTEM_PROMPT = """You are a goal extraction agent for a multiparty session type (MPST) system.

Given a user's intent (natural language) and a protocol structure, you extract
concrete, math-checkable goals. Each goal must be:

1. ANCHORED to a specific message in the protocol (sender, receiver, label)
2. EXPRESSED as a Python predicate over the variable `x` (the message payload)
3. MEASURABLE — has a clear pass/fail criterion

Output format — return a JSON array of goal objects:
```json
[
  {
    "id": "G1",
    "description": "Revenue must exceed $50,000 for high-path",
    "metric": "revenue_amount",
    "predicate": "x > 50000",
    "anchor_sender": "Fetcher",
    "anchor_receiver": "TaxSpecialist",
    "anchor_label": "HighRevenue",
    "threshold": "> 50000",
    "verification": "runtime"
  }
]
```

Rules:
- Every goal MUST reference a real message in the protocol (sender, receiver, label must match)
- Predicates use Python syntax: `x > 0`, `len(x) > 0`, `x >= 0.95`, `"approved" in x`
- Use `x` as the bound variable (the payload value)
- Prefer simple, auditable predicates
- Mark goals as "static" if they can be checked at compile time, "runtime" if they need execution data
- If a goal cannot be anchored to any message, report it as a warning
"""


def elicit_goals_from_intent(
    intent: str,
    protocol: ParsedProtocol,
    llm_client=None,
    mock: bool = False
) -> GoalSet:
    """
    Extract math-checkable goals from user intent.

    Args:
        intent: Natural language description of what the user wants
        protocol: Parsed protocol to anchor goals to
        llm_client: LLM client (None for mock mode)
        mock: If True, return hardcoded goals for finance demo

    Returns:
        GoalSet with anchored goals
    """
    if mock:
        return _mock_finance_goals(intent, protocol)

    # Build protocol context for the LLM
    protocol_context = _build_protocol_context(protocol)

    user_prompt = f"""Intent: {intent}

Protocol structure:
{protocol_context}

Extract all math-checkable goals from this intent. Anchor each goal to a specific
message in the protocol. Return ONLY a JSON array of goal objects."""

    response = llm_client.generate(GOAL_ELICITATION_SYSTEM_PROMPT, user_prompt)

    return _parse_llm_goals(intent, response, protocol)


def _build_protocol_context(protocol: ParsedProtocol) -> str:
    """Build a text description of the protocol for the LLM."""
    lines = [f"Protocol: {protocol.protocol_name}"]
    lines.append(f"Roles: {', '.join(protocol.roles)}")
    lines.append("Messages:")
    for msg in protocol.messages:
        lines.append(f"  {msg.sender} -> {msg.receiver} : {msg.message_name}({msg.payload_type})")
    if protocol.choice_roles:
        lines.append(f"Choice points: {', '.join(protocol.choice_roles)}")
    return "\n".join(lines)


def _parse_llm_goals(intent: str, response: str, protocol: ParsedProtocol) -> GoalSet:
    """Parse LLM response into a GoalSet, validating anchors against protocol."""
    goal_set = GoalSet(intent=intent)

    # Extract JSON from response
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if not json_match:
        goal_set.warnings.append("LLM did not return valid JSON array")
        return goal_set

    try:
        goals_data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        goal_set.warnings.append(f"JSON parse error: {e}")
        return goal_set

    # Validate and create goals
    valid_messages = {(m.sender, m.receiver, m.message_name) for m in protocol.messages}

    for g in goals_data:
        anchor = (g.get("anchor_sender", ""), g.get("anchor_receiver", ""), g.get("anchor_label", ""))
        if anchor not in valid_messages:
            goal_set.warnings.append(
                f"Goal {g.get('id', '?')}: anchor {anchor} not found in protocol. "
                f"Available: {sorted(valid_messages)}"
            )
            continue

        goal_set.goals.append(Goal(
            id=g.get("id", f"G{len(goal_set.goals)+1}"),
            description=g.get("description", ""),
            metric=g.get("metric", ""),
            predicate=g.get("predicate", "True"),
            anchor_sender=g["anchor_sender"],
            anchor_receiver=g["anchor_receiver"],
            anchor_label=g["anchor_label"],
            threshold=g.get("threshold", ""),
            verification=g.get("verification", "runtime"),
        ))

    return goal_set


def _mock_finance_goals(intent: str, protocol: ParsedProtocol) -> GoalSet:
    """Hardcoded goals for the finance demo protocol."""
    return GoalSet(
        intent=intent,
        goals=[
            Goal(
                id="G1",
                description="High-path revenue must exceed $50,000",
                metric="revenue_amount",
                predicate="float(x) > 50000",
                anchor_sender="Fetcher",
                anchor_receiver="TaxSpecialist",
                anchor_label="HighRevenue",
                threshold="> 50000",
                verification="runtime",
            ),
            Goal(
                id="G2",
                description="Audit result must be non-empty",
                metric="audit_completeness",
                predicate="len(x) > 0",
                anchor_sender="TaxSpecialist",
                anchor_receiver="RevenueAnalyst",
                anchor_label="AuditedRevenue",
                threshold="non-empty string",
                verification="runtime",
            ),
            Goal(
                id="G3",
                description="Revenue audit must be explicitly approved",
                metric="audit_approval",
                predicate='"approved" in x.lower() or "ok" in x.lower()',
                anchor_sender="TaxVerifier",
                anchor_receiver="RevenueAnalyst",
                anchor_label="RevenueAuditApproval",
                threshold="contains 'approved' or 'ok'",
                verification="runtime",
            ),
            Goal(
                id="G4",
                description="Revenue analysis must be substantive (>10 chars)",
                metric="analysis_quality",
                predicate="len(x) > 10",
                anchor_sender="RevenueAnalyst",
                anchor_receiver="Writer",
                anchor_label="RevenueAnalysis",
                threshold="> 10 characters",
                verification="runtime",
            ),
            Goal(
                id="G5",
                description="Expense analysis must be substantive (>10 chars)",
                metric="expense_quality",
                predicate="len(x) > 10",
                anchor_sender="ExpenseAnalyst",
                anchor_receiver="Writer",
                anchor_label="ExpenseAnalysis",
                threshold="> 10 characters",
                verification="runtime",
            ),
        ]
    )


def verify_goals_against_trace(
    goal_set: GoalSet,
    trace_events: list,
    branch: str | None = None,
    match_labels: bool = True,
) -> dict[str, tuple[bool, str]]:
    """
    Post-execution verification: check each goal against the trace.

    Returns dict: goal_id -> (passed, detail_message)

    branch: the branch hint of the trial being evaluated. A goal that
    declares a `branch` different from this one belongs to a protocol path
    the trial did not take, and is reported as vacuously satisfied (True)
    instead of failed for a missing anchor. Goals with no `branch` are
    mandatory on every branch. Pass branch=None to disable this skipping.

    match_labels: True (default) is the STRICT rule — the event must match
    the goal's (sender, receiver, label) exactly. False is the FAIR rule
    for arms that were never shown the protocol's message labels (e.g. the
    bare arm): any event between the goal's sender and receiver whose
    payload satisfies the predicate counts, whatever label the agents
    chose. Without this, a bare-arm agent that sends the right content to
    the right peer under a self-invented label would score zero — grading
    it on vocabulary it was never given.
    """
    from stjp_core.compiler.refinement_checker import Refinement

    results = {}
    for goal in goal_set.goals:
        # Branch-conditional goal off its branch -> vacuously satisfied.
        # Fixes branch-asymmetric goals: e.g. a high-revenue goal simply has
        # no anchor event on a standard-branch trial, and must not fail it.
        if goal.branch and branch is not None and goal.branch != branch:
            results[goal.id] = (True, f"VACUOUS: {goal.id} applies only to "
                                      f"branch '{goal.branch}'; trial branch "
                                      f"is '{branch}'")
            continue

        # Find the matching event in the trace
        matching = [e for e in trace_events
                    if e.sender == goal.anchor_sender
                    and e.receiver == goal.anchor_receiver
                    and (not match_labels or e.label == goal.anchor_label)]

        if not matching:
            want = (f"{goal.anchor_sender}->{goal.anchor_receiver}"
                    + (f":{goal.anchor_label}" if match_labels else " (any label)"))
            results[goal.id] = (False, f"Anchor message not found in trace: {want}")
            continue

        refn = Refinement(
            sender=goal.anchor_sender,
            receiver=goal.anchor_receiver,
            label=goal.anchor_label,
            predicates=[goal.predicate],
        )
        if match_labels:
            # Strict: judge the first exactly-matching event (unchanged
            # historical semantics — do not silently alter old results).
            event = matching[0]
            ok, err = refn.check(event.payload)
        else:
            # Label-free: ANY event on the role pair that satisfies the
            # predicate counts (mirrors evaluate_run.verify_role_pair).
            ok, err, event = False, "", matching[0]
            for e in matching:
                e_ok, e_err = refn.check(e.payload)
                if e_ok:
                    ok, err, event = True, "", e
                    break
                err = e_err
        if ok:
            results[goal.id] = (True, f"PASS: {goal.description} (payload={event.payload!r})")
        else:
            results[goal.id] = (False, f"FAIL: {goal.description}: {err} (payload={event.payload!r})")

    return results
