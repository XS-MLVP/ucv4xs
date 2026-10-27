"""Independent event-level oracle; no DUT, signal bundle or simulator needed."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import CheckContext, ScoreboardMismatch, ScoreboardMode

from bpuverify.ubtb.checker.semantic import UbtbSemanticChecker
from bpuverify.ubtb.model.semantic import UbtbEvents, UbtbReference, _RecencyTree
from bpuverify.ubtb.transaction.types import (
    BranchTraining, PredictRequest, UbtbBatchTraining, UbtbBranchFeedback,
)


FIRST = BranchTraining(0x80001000, 0x80002340, 1, 3, 2)


def learn(model, feedback):
    model.advance(UbtbEvents(fast_feedback=feedback))
    model.advance(UbtbEvents())


def predict(model, pc):
    return model.advance(UbtbEvents(predict=PredictRequest(pc)))


def test_feedback_acceptance_is_not_commit_and_reset_cancels_pending():
    model = UbtbReference()
    model.advance(UbtbEvents(fast_feedback=FIRST))
    assert all(entry.confidence == 0 for entry in model.entries)
    # Lookup sees the pre-commit cache, not an eagerly updated golden state.
    assert predict(model, FIRST.pc).valid == 0
    assert predict(model, FIRST.pc).target == FIRST.target
    model.advance(UbtbEvents(fast_feedback=replace(FIRST, target=FIRST.target + 0x100)))
    assert model.learning is not None
    model.advance(UbtbEvents(reset=True))
    assert model.learning is None and model.lookup is None
    assert not predict(model, FIRST.pc).valid


@pytest.mark.parametrize('field,value', [('target', 0x80004340), ('position', 9),
                                       ('branch_type', 3), ('ras_action', 2), ('taken', 0)])
def test_mismatch_ages_old_payload_before_replacement(field, value):
    model = UbtbReference()
    learn(model, FIRST)
    changed = replace(FIRST, **{field: value})
    for confidence in (2, 1, 0):
        learn(model, changed)
        assert model.entries[0].confidence == confidence
        actual = predict(model, FIRST.pc)
        assert actual.valid == int(confidence > 0)
        if confidence:
            assert (actual.target, actual.position, actual.branch_type, actual.ras_action) == (
                FIRST.target, FIRST.position, FIRST.branch_type, FIRST.ras_action)
    learn(model, changed)
    assert predict(model, FIRST.pc).valid == changed.taken
    if changed.taken:
        entry = model.entries[0]
        assert (entry.target, entry.position, entry.branch_type, entry.ras_action) == (
            changed.target & model.target_mask, changed.position,
            changed.branch_type, changed.ras_action)


def test_exact_match_recovers_and_saturates_and_missing_not_taken_does_not_allocate():
    model = UbtbReference()
    learn(model, replace(FIRST, taken=0))
    assert not predict(model, FIRST.pc).valid
    learn(model, FIRST)
    learn(model, replace(FIRST, taken=0))
    assert model.entries[0].confidence == 2
    for _ in range(8):
        learn(model, FIRST)
        assert model.entries[0].confidence == 3


def test_contiguous_feedback_forwards_both_payload_and_confidence():
    model = UbtbReference()
    bad = replace(FIRST, taken=0)
    changed = replace(FIRST, target=FIRST.target + 0x200, position=8, ras_action=2)
    for feedback in (FIRST, bad, bad, bad, changed, changed):
        model.advance(UbtbEvents(fast_feedback=feedback))
    model.advance(UbtbEvents())
    assert sum(entry.confidence > 0 for entry in model.entries) == 1
    assert model.entries[0].confidence == 3
    result = predict(model, FIRST.pc)
    assert (result.target, result.position, result.ras_action) == (changed.target, 8, 2)


def test_contiguous_fallthrough_cannot_revive_depleted_entry():
    model = UbtbReference()
    conditional = replace(FIRST, branch_type=1)
    for feedback in (conditional, *(replace(conditional, taken=0) for _ in range(4))):
        model.advance(UbtbEvents(fast_feedback=feedback))
    model.advance(UbtbEvents())
    assert not predict(model, FIRST.pc).valid
    assert all(entry.confidence == 0 for entry in model.entries)


def test_wrong_encoded_pc_cannot_pass_by_agreeing_with_the_wrong_dut_input():
    checker = UbtbSemanticChecker()
    for tick, events in ((0, UbtbEvents(reset=True)), (2, UbtbEvents(fast_feedback=FIRST)),
                         (4, UbtbEvents()), (6, UbtbEvents(predict=PredictRequest(FIRST.pc)))):
        checker.capture_input(SimpleNamespace(tick=tick), events)
        checker.capture_output(SimpleNamespace(tick=tick + 1), checker.model.prediction(), enabled=True)
    request = PredictRequest(FIRST.pc + 2)
    compare = checker.response_expected(request, CheckContext(
        checker.board.name, ScoreboardMode.ASYNC, request=request,
        accepted_event=SimpleNamespace(tick=5)))
    with pytest.raises(ScoreboardMismatch):
        compare(checker.model.prediction())


@pytest.mark.parametrize('branch_type,ras_action', [(1, 0), (2, 0), (2, 2), (3, 0),
                                                 (3, 1), (3, 2), (3, 3)])
@pytest.mark.parametrize('slot', [0, 3, 7])
def test_resolve_selects_valid_mispredict_not_other_slots_or_fast(slot, branch_type, ras_action):
    model = UbtbReference()
    branch = UbtbBranchFeedback(0x80003000, 1, slot * 2, branch_type,
                               ras_action=ras_action, mispredict=1)
    earlier = (UbtbBranchFeedback(0x80004000, 1, 0, 1),) * slot
    batch = UbtbBatchTraining(FIRST.pc + 0x80, (*earlier, branch))
    model.advance(UbtbEvents(resolve_feedback=batch, fast_feedback=FIRST))
    model.advance(UbtbEvents())
    result = predict(model, batch.pc)
    assert (result.valid, result.target, result.position, result.branch_type,
            result.ras_action) == (1, branch.target, slot * 2, branch_type, ras_action)
    assert not predict(model, FIRST.pc).valid


@pytest.mark.parametrize('reason', ['correct', 'invalid', 'not-fired'])
def test_unqualified_resolve_falls_back_to_fast_feedback(reason):
    branch = UbtbBranchFeedback(0x80003000, 1, 4, 3, mispredict=int(reason != 'correct'),
                               valid=int(reason != 'invalid'))
    batch = UbtbBatchTraining(FIRST.pc + 0x80, (branch,), fire=int(reason != 'not-fired'))
    model = UbtbReference()
    model.advance(UbtbEvents(resolve_feedback=batch, fast_feedback=FIRST))
    model.advance(UbtbEvents())
    assert predict(model, FIRST.pc).target == FIRST.target
    assert not predict(model, batch.pc).valid


def test_enable_gates_acceptance_not_prior_accepted_effect():
    model = UbtbReference()
    model.advance(UbtbEvents(fast_feedback=FIRST, enabled=False))
    model.advance(UbtbEvents())
    assert not predict(model, FIRST.pc).valid
    model.advance(UbtbEvents(fast_feedback=FIRST))
    model.advance(UbtbEvents(enabled=False))
    assert not model.prediction(enabled=False).valid
    assert predict(model, FIRST.pc).target == FIRST.target


def test_partial_tag_alias_and_target_region_are_model_owned():
    model = UbtbReference()
    learn(model, FIRST)
    alias = FIRST.pc + (1 << 23)
    result = predict(model, alias)
    assert result.target == FIRST.target + (1 << 23)
    assert predict(model, FIRST.pc + 2).valid == 0
    # Carry correction is disabled in this config; high target bits are not
    # stored. This is not a full-address ideal BTB masquerading as the oracle.
    model = UbtbReference()
    learn(model, replace(FIRST, target=FIRST.target + (1 << 22)))
    assert predict(model, FIRST.pc).target == FIRST.target + (1 << 22)
    model = UbtbReference()
    learn(model, replace(FIRST, target=FIRST.target + (1 << 23)))
    assert predict(model, FIRST.pc).target == FIRST.target


def fill(model):
    values = tuple(replace(FIRST, pc=FIRST.pc + 0x20 * index,
                           target=FIRST.target + 0x20 * index) for index in range(32))
    for value in values:
        learn(model, value)
    return values


def test_tree_recency_has_hand_derived_four_way_choices():
    tree = _RecencyTree(4)
    assert tree.victim() == 0
    choices = []
    for slot in (0, 1, 2, 3):
        tree.touch(slot)
        choices.append(tree.victim())
    assert choices == [2, 2, 0, 0]
    tree.touch(0)
    assert tree.victim() == 2


@pytest.mark.parametrize('same_clock_lookup', ['victim', 'survivor', 'new-key'])
def test_capacity_replacement_uses_own_victim_and_suppresses_only_old_key(same_clock_lookup):
    model = UbtbReference()
    values = fill(model)
    victim = model.victim()
    replacement = replace(FIRST, pc=FIRST.pc + 0x1000, target=FIRST.target + 0x1000)
    model.advance(UbtbEvents(fast_feedback=replacement, consume=False))
    survivor = (victim + 1) % 32
    pc = dict(victim=values[victim].pc, survivor=values[survivor].pc,
              **{'new-key': replacement.pc})[same_clock_lookup]
    result = model.advance(UbtbEvents(predict=PredictRequest(pc), consume=False))
    assert result.valid == int(same_clock_lookup == 'survivor')
    assert predict(model, replacement.pc).target == replacement.target
    assert not predict(model, values[victim].pc).valid


def test_contiguous_replacement_does_not_false_hit_evicted_key():
    model = UbtbReference()
    values = fill(model)
    victim = model.victim()
    replacement = replace(FIRST, pc=FIRST.pc + 0x1000)
    model.advance(UbtbEvents(fast_feedback=replacement, consume=False))
    old = replace(values[victim], taken=0)
    model.advance(UbtbEvents(fast_feedback=old, consume=False))
    model.advance(UbtbEvents(consume=False))
    assert predict(model, replacement.pc).valid
    assert not predict(model, old.pc).valid
    assert sum(entry.confidence > 0 for entry in model.entries) == 32


def test_pending_lookup_holds_when_no_new_request_and_touch_requires_consume():
    model = UbtbReference()
    learn(model, FIRST)
    expected = predict(model, FIRST.pc)
    before = tuple(model.recency.older)
    assert model.advance(UbtbEvents(consume=False)) == expected
    assert tuple(model.recency.older) == before
    # Its key was latched at request time; an unrelated input PC never enters
    # the model unless there is an accepted prediction event.
    assert model.advance(UbtbEvents(consume=False)) == expected


@pytest.mark.parametrize('field', ['target', 'position', 'branch_type', 'ras_action', 'taken', 'valid'])
def test_wrong_actual_fails_with_point_and_reference_state_without_seeding(field):
    checker = UbtbSemanticChecker()
    for tick, events in ((0, UbtbEvents(reset=True)), (2, UbtbEvents(fast_feedback=FIRST)),
                         (4, UbtbEvents()), (6, UbtbEvents(predict=PredictRequest(FIRST.pc)))):
        checker.capture_input(SimpleNamespace(tick=tick), events)
        expected = checker.model.prediction()
        checker.capture_output(SimpleNamespace(tick=tick + 1), expected, enabled=True)
    before = checker.model.state()
    expected = checker.model.prediction()
    wrong = replace(expected, **{field: getattr(expected, field) ^ 1})
    checker.capture_input(SimpleNamespace(tick=8), UbtbEvents(consume=False))
    checker.capture_output(SimpleNamespace(tick=9), wrong, enabled=True)
    with pytest.raises(ScoreboardMismatch) as caught:
        checker.raise_failure()
    assert field in str(caught.value)
    assert 'state' in str(caught.value) and 'sequence_id: 9' in str(caught.value)
    assert checker.model.state() == before


def test_invalid_response_payload_is_unqualified_and_missing_clock_is_failure():
    checker = UbtbSemanticChecker()
    checker.capture_input(SimpleNamespace(tick=0), UbtbEvents(reset=True))
    miss = replace(checker.model.prediction(), target=0x1, position=9, taken=1, branch_type=3)
    checker.capture_output(SimpleNamespace(tick=1), miss, enabled=True)
    checker.raise_failure()
    checker.capture_output(SimpleNamespace(tick=3), miss, enabled=True)
    with pytest.raises(AssertionError, match='input boundary'):
        checker.raise_failure()


def test_reset_idle_valid_is_not_a_response_but_new_request_is_checked():
    checker = UbtbSemanticChecker()
    idle_bits = replace(checker.model.prediction(), valid=1)
    for tick, events in ((0, UbtbEvents(reset=True)), (2, UbtbEvents())):
        checker.capture_input(SimpleNamespace(tick=tick), events)
        checker.capture_output(SimpleNamespace(tick=tick + 1), idle_bits, enabled=True)
    checker.raise_failure()
    assert checker.board.status.checked == 0
    checker.capture_input(SimpleNamespace(tick=4), UbtbEvents(predict=PredictRequest(FIRST.pc)))
    checker.capture_output(SimpleNamespace(tick=5), idle_bits, enabled=True)
    with pytest.raises(ScoreboardMismatch):
        checker.raise_failure()
    # Teardown must not add a duplicate ERROR to an already observed FAIL.
    checker.raise_unobserved_failure()


@pytest.mark.parametrize('bad', [replace(FIRST, pc=-1), replace(FIRST, target=1 << 50),
                               replace(FIRST, position=32), replace(FIRST, taken=2)])
def test_out_of_contract_inputs_raise_instead_of_silent_truncation(bad):
    with pytest.raises(ValueError):
        UbtbReference().advance(UbtbEvents(fast_feedback=bad))
