"""formalize.py tests against the REAL Scribble toolchain (no mocking of the
validator — per the program's real-toolchain mandate,
`SEAM_TRAINING_EXECUTION_PLAN.md` §2 "Real toolchain mandate (hard rule)").

Two paths are exercised:

  1. A vendored `skills_safety` set (pr_merge) run through the ACTUAL
     --no-llm formalize pipeline. This is the empirical funnel result this
     task reports: real, unformatted skill prose has no fenced
     ```localtype block and doesn't match the strict STJP `*_skills.md`
     heading format, so deterministic compaction cannot proceed and the
     team is dropped at `compactor_survived` with a specific, legible
     reason — proving the fail path is real, not a bug.

  2. A synthetic 4-role team WITH fenced localtype blocks (the same escrow
     trade fixture `stjp_core/tests/test_skill_compactor.py` uses) to prove
     the success path: compaction -> compatibility -> deterministic
     synthesis -> REAL Scribble validation -> DatasetRecord, end to end.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MINING_DIR = HERE.parent
REPO_ROOT = MINING_DIR.parents[2]
sys.path.insert(0, str(MINING_DIR))
sys.path.insert(0, str(REPO_ROOT))

from harvest import Artifact, adapter_local_vendored        # noqa: E402
from ledger import build_ledger                              # noqa: E402
from team_builder import build_teams                          # noqa: E402
from formalize import (                                       # noqa: E402
    run_formalize, formalize_team, assert_toolchain, ToolchainMissing,
    FunnelStats)
from intent_extract import extract_intent                     # noqa: E402
from schema import DatasetRecord                               # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _toolchain():
    try:
        assert_toolchain()
    except ToolchainMissing as e:
        pytest.skip(f"real Scribble toolchain not wired: {e}")


def _art(role_hint, text, source_repo="fixture/escrow", path=None) -> Artifact:
    return Artifact(
        artifact_id=f"escrow:{role_hint}", source_repo=source_repo,
        path=path or f"{role_hint}.md", role_hint=role_hint, text=text,
        frontmatter={}, adapter="test_fixture", retrieval_route="local-vendored")


BUYER = """# Buyer
You are the Buyer in an escrow-protected trade.

```localtype
Escrow!Deposit(Double);
Carrier?DeliverGoods(String);
Escrow!ConfirmReceipt(String);
Escrow?SettlementComplete(String);
```
"""

SELLER = """# Seller
```localtype
Escrow?PaymentSecured(String);
Carrier!ShipGoods(String);
Escrow?SettlementComplete(String);
```
"""

ESCROW = """# Escrow
```localtype
Buyer?Deposit(Double);
Seller!PaymentSecured(String);
Buyer?ConfirmReceipt(String);
Buyer!SettlementComplete(String);
Seller!SettlementComplete(String);
```
"""

CARRIER = """# Carrier
```localtype
Seller?ShipGoods(String);
Buyer!DeliverGoods(String);
```
"""


def test_real_pr_merge_team_drops_at_compaction_no_llm():
    cases_dir = REPO_ROOT / "experiments" / "cases" / "skills_safety"
    artifacts = adapter_local_vendored(cases_dir)
    ledger = build_ledger(artifacts)
    result = build_teams(artifacts)
    pr_merge_team = next(t for t in result.teams if t.team_id == "worked_example:pr_merge")

    artifacts_by_id = {a.artifact_id: a for a in artifacts}
    intents = {aid: extract_intent(a) for aid, a in artifacts_by_id.items()}
    funnel = FunnelStats()
    res = formalize_team(pr_merge_team, artifacts_by_id, ledger, intents, funnel)

    assert res.ok is False
    assert res.stage_reached == "compactor_survived"
    assert res.record is None
    assert funnel.counts["team_license_ok"] == 1
    assert funnel.counts["compactor_survived"] == 0
    assert any("compactor_survived" in k for k in funnel.drop_reasons)


def test_synthetic_escrow_team_survives_end_to_end_with_real_scribble(monkeypatch):
    # Register a permissive test-only license fact so the ledger doesn't
    # quarantine this synthetic fixture repo (it isn't a real harvested
    # source, so it has no entry in ledger.REPO_LICENSES).
    import ledger as ledger_mod
    monkeypatch.setitem(ledger_mod.REPO_LICENSES, "fixture/escrow", {
        "spdx": "MIT", "quote": "test fixture, not a real license", "commit_sha": "0" * 40})

    members = [_art("Buyer", BUYER), _art("Seller", SELLER),
              _art("Escrow", ESCROW), _art("Carrier", CARRIER)]
    from team_builder import Team
    team = Team(team_id="test:escrow_trade", source_repo="fixture/escrow",
               artifact_ids=[m.artifact_id for m in members],
               role_names=[m.role_hint for m in members], heuristic="test-fixture")
    artifacts_by_id = {m.artifact_id: m for m in members}
    ledger = build_ledger(members)
    intents = {m.artifact_id: extract_intent(m) for m in members}
    funnel = FunnelStats()

    res = formalize_team(team, artifacts_by_id, ledger, intents, funnel)

    assert res.ok is True, res.error
    assert res.stage_reached == "validator_passed"
    assert res.record is not None
    assert isinstance(res.record, DatasetRecord)
    assert res.record.source == "mined"
    assert res.record.split == "test-real"
    assert "Deposit" in res.record.protocol
    assert res.record.gen["family_placeholder"] is True
    assert res.record.provenance["team_id"] == "test:escrow_trade"
    assert funnel.counts["validator_passed"] == 1


def test_quarantined_member_drops_team_before_compaction():
    restricted = _art("DocxHelper", "some prose", source_repo="anthropics/skills",
                      path="skills/docx/SKILL.md")
    other = _art("Reviewer", "more prose", source_repo="anthropics/skills",
                 path="skills/other/SKILL.md")
    from team_builder import Team
    team = Team(team_id="test:quarantine", source_repo="anthropics/skills",
               artifact_ids=[restricted.artifact_id, other.artifact_id],
               role_names=["DocxHelper", "Reviewer"], heuristic="test-fixture")
    artifacts_by_id = {restricted.artifact_id: restricted, other.artifact_id: other}
    ledger = build_ledger([restricted, other])
    intents = {a.artifact_id: extract_intent(a) for a in [restricted, other]}
    funnel = FunnelStats()

    res = formalize_team(team, artifacts_by_id, ledger, intents, funnel)

    assert res.ok is False
    assert res.stage_reached == "team_license_ok"
    assert funnel.counts["team_license_ok"] == 0


def test_run_formalize_end_to_end_on_all_vendored_teams_is_toolchain_safe():
    """Full driver over the 6 vendored teams — must complete without
    raising, even though (per the two tests above) every one of them drops
    at compaction under --no-llm. This is the "prove the pipeline runs"
    smoke test the task card asks for."""
    cases_dir = REPO_ROOT / "experiments" / "cases" / "skills_safety"
    artifacts = adapter_local_vendored(cases_dir)
    ledger = build_ledger(artifacts)
    team_result = build_teams(artifacts)
    worked = [t for t in team_result.teams if t.heuristic == "worked-example"
             and t.source_repo == "in-repo:skills_safety"]
    assert len(worked) == 6

    records, funnel, results = run_formalize(artifacts, worked, ledger)

    assert len(results) == 6
    assert funnel.counts["harvested"] == len(artifacts)
    # content_pipeline dropped from 6 to 5 on 2026-07-12: its upstream
    # crewAIInc/crewAI-examples was verified to carry NO license (W20), so
    # the ledger no longer marks it permissive. The other 5 vendored teams
    # remain licensed. See docs/reference/MINED_SKILLS_SOURCES.md.
    assert funnel.counts["team_license_ok"] == 5
    # honest, expected result under the --no-llm constraint (see task
    # report for the full discussion):
    assert funnel.counts["compactor_survived"] == 0
    assert len(records) == 0
