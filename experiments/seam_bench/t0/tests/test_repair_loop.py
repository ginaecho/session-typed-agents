"""test_repair_loop.py — the T+R production loop, fully offline with
MockDrafter and fake validate/bisim callables (no subprocess, no real
Scribble call — validity.py itself is exercised separately, end-to-end
against the real toolchain, by test_gold_pairs.py and eval/tests/).

Task card item 5's three named scenarios:
  - repair loop terminates and caps at 3
  - a MockDrafter that returns gold yields validity@1=1.0
  - one that returns garbage then gold yields validity@1=0, repair-rounds=1
plus a check that the produced RunRecords wire correctly through W1's
metrics.py (that's the whole point of matching W1's RunRecord shape).
"""
from experiments.seam_bench.eval import metrics
from experiments.seam_bench.t0 import repair_loop
from experiments.seam_bench.t0.drafter import MockDrafter

GOLD = "protocol Gold(role A, role B) { Msg() from A to B; }"
GARBAGE = "protocol Garbage(role A) { this is not valid }"
INTENT = "send a message from A to B"


def fake_validate(text: str) -> tuple[bool, str]:
    if text == GOLD:
        return True, ""
    return False, "mismatched input: not valid Scribble"


def fake_bisim(a: str, b: str) -> tuple[bool, str]:
    return (a == b), ("equivalent" if a == b else "not equivalent")


def test_mock_drafter_returning_gold_yields_validity_at_1_of_1():
    drafter = MockDrafter(draft_script={INTENT: [GOLD]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-gold", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, validate_fn=fake_validate,
        bisim_fn=fake_bisim)

    assert len(records) == 1
    r = records[0]
    assert r.k == 1
    assert r.valid is True
    assert r.repair_rounds == 0
    assert r.bisim is True

    value, n = metrics.validity_at_1(records)
    assert (value, n) == (1.0, 1)


def test_garbage_then_gold_repair_yields_validity_at_1_zero_repair_rounds_one():
    drafter = MockDrafter(draft_script={INTENT: [GARBAGE]},
                           repair_script={INTENT: [GOLD]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-repair", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, validate_fn=fake_validate,
        bisim_fn=fake_bisim)

    assert len(records) == 2
    first, second = sorted(records, key=lambda r: r.k)
    assert first.k == 1 and first.valid is False
    assert second.k == 2 and second.valid is True
    # repair_rounds is the chain's FINAL total-rounds-used, recorded on
    # every row (see repair_loop.py docstring) -- both rows read 1 here.
    assert first.repair_rounds == 1
    assert second.repair_rounds == 1
    assert second.bisim is True
    assert first.bisim is None  # never validated -> nothing to compare

    value, n = metrics.validity_at_1(records)
    assert (value, n) == (0.0, 1)

    mean, n_rounds = metrics.repair_rounds_mean(records)
    assert (mean, n_rounds) == (1.0, 1)


def test_repair_loop_terminates_and_caps_at_3():
    # A drafter that never produces anything valid, ever.
    drafter = MockDrafter(draft_script={INTENT: [GARBAGE]},
                           repair_script={INTENT: [GARBAGE]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-hopeless", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, max_rounds=3, validate_fn=fake_validate,
        bisim_fn=fake_bisim)

    # 1 initial draft + 3 repair attempts, never more.
    assert len(records) == 4
    assert [r.k for r in records] == [1, 2, 3, 4]
    assert all(r.valid is False for r in records)
    assert all(r.repair_rounds == 3 for r in records)
    assert all(r.bisim is None for r in records)

    value, n = metrics.validity_at_1(records)
    assert (value, n) == (0.0, 1)
    mean, n_rounds = metrics.repair_rounds_mean(records)
    assert (mean, n_rounds) == (3.0, 1)


def test_repair_loop_respects_a_smaller_max_rounds_cap():
    drafter = MockDrafter(draft_script={INTENT: [GARBAGE]},
                           repair_script={INTENT: [GARBAGE]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-cap1", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, max_rounds=1, validate_fn=fake_validate,
        bisim_fn=fake_bisim)
    assert len(records) == 2  # 1 initial + 1 repair, capped
    assert all(r.repair_rounds == 1 for r in records)


def test_repair_loop_no_gold_means_bisim_always_none():
    drafter = MockDrafter(draft_script={INTENT: [GOLD]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-nogold", item_id="item-1", split="dev",
        intent=INTENT, gold=None, validate_fn=fake_validate,
        bisim_fn=fake_bisim)
    assert records[0].valid is True
    assert records[0].bisim is None


def test_repair_loop_reuses_caller_supplied_initial_draft():
    # A drafter whose draft() would raise if called -- proves
    # initial_draft short-circuits the initial drafter.draft() call.
    class NoInitialDraft(MockDrafter):
        def draft(self, intent, k, exemplars=None):
            raise AssertionError("draft() should not be called when "
                                  "initial_draft is supplied")

    drafter = NoInitialDraft(repair_script={INTENT: [GOLD]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-reuse", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, initial_draft=GARBAGE,
        validate_fn=fake_validate, bisim_fn=fake_bisim)
    assert len(records) == 2
    assert records[0].draft == GARBAGE
    assert records[1].valid is True


def test_repair_loop_splits_guard_sidecar_before_validating():
    drafted_with_sidecar = GOLD + "\n=== REFN ===\n[A -> B : Msg]\nrequire: x > 0\n"
    drafter = MockDrafter(draft_script={INTENT: [drafted_with_sidecar]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-sidecar", item_id="item-1", split="dev",
        intent=INTENT, gold=GOLD, validate_fn=fake_validate,
        bisim_fn=fake_bisim)
    assert len(records) == 1
    assert records[0].valid is True  # fake_validate only recognizes bare GOLD
    # the RunRecord keeps the FULL text (protocol + sidecar) so guard
    # co-emission can be measured downstream.
    assert records[0].draft == drafted_with_sidecar


def test_required_guard_sidecar_is_repaired_before_acceptance():
    guarded = GOLD + "\n=== REFN ===\nMsg.amount :: amount > 0\n"
    drafter = MockDrafter(draft_script={INTENT: [GOLD]},
                           repair_script={INTENT: [guarded]})
    records = repair_loop.run_repair_chain(
        drafter, system="s-required-sidecar", item_id="item-1", split="dev",
        intent=INTENT, validate_fn=fake_validate,
        require_guard_sidecar=True)

    assert [record.valid for record in records] == [False, True]
    assert "missing required refinement-guard sidecar" in \
        records[0].validator_msg
    assert records[1].draft == guarded


def test_repair_chain_reports_each_validation_and_repair_stage():
    events = []
    drafter = MockDrafter(draft_script={INTENT: [GARBAGE]},
                           repair_script={INTENT: [GOLD]})

    repair_loop.run_repair_chain(
        drafter, system="s-progress", item_id="item-1", split="dev",
        intent=INTENT, validate_fn=fake_validate,
        progress=lambda stage, detail: events.append((stage, detail)))

    assert [stage for stage, _detail in events] == [
        "validation_started", "validation_result", "repair_started",
        "repair_completed", "validation_started", "validation_result"]
    results = [detail for stage, detail in events
               if stage == "validation_result"]
    assert [result["valid"] for result in results] == [False, True]


def test_validator_timeout_retries_same_draft_without_llm_repair():
    calls = []
    events = []

    def flaky_validate(text):
        calls.append(text)
        if len(calls) == 1:
            return False, "verifier worker exceeded 30.0s and was killed"
        return True, ""

    drafter = MockDrafter(draft_script={INTENT: [GOLD]})
    records = repair_loop.run_repair_chain(
        drafter, system="infra-retry", item_id="item-1", split="dev",
        intent=INTENT, validate_fn=flaky_validate,
        progress=lambda stage, detail: events.append((stage, detail)))

    assert calls == [GOLD, GOLD]
    assert len(records) == 1 and records[0].valid
    assert any(stage == "validation_infrastructure_retry"
               for stage, _detail in events)
    assert not any(stage == "repair_started" for stage, _detail in events)
