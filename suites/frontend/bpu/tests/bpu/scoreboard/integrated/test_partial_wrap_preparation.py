"""Preparation predicates cannot substitute a priority hit for fallback."""
from copy import deepcopy

import pytest
from toffee import Scoreboard, ScoreboardMismatch

from bpuverify.bpu.model.bypass.model import BypassReference
from bpuverify.bpu.model.bypass.partial_wrap import filled_with, retained_fallback, qualifies_return_request
from bpuverify.bpu.case.bypass.two_program_plan import recipe
from bpuverify.bpu.case.bypass.public_readback import public_readback_pair
from bpuverify.bpu.model.phr.model import MASK, path_hash, fold, folds
from tests.bpu.scoreboard.integrated.test_coverage_collection import inputs


def allocate(reference, index, tag):
    reference.advance(inputs(train_index=index))
    reference.advance(inputs(train_index=index, allocate=1, allocate_taken=1,
                             allocate_position=6, tag=tag))


def test_reset_and_priority_hits_are_not_preparation_success():
    reference = BypassReference(1)
    assert retained_fallback(reference, 25) is None
    allocate(reference, 25, 99)
    assert retained_fallback(reference, 25) is None
    assert not filled_with(reference, 25, dict(counter=4))


def test_partial_wrap_preserves_old_payload_above_prefix_without_state_seeding():
    reference = BypassReference(1)
    for _ in range(8):
        allocate(reference, 25, 99)
    expected = dict(data_valid=1, tag=99, position=6, counter=4)
    assert filled_with(reference, 25, expected)
    for _ in range(3):
        allocate(reference, 254, 93)
    before = deepcopy(reference.state())
    assert retained_fallback(reference, 25) == dict(
        index=25, slot=7, hits=0b11111000, mask=0b111, enq=11, deq=reference.deq)
    assert reference.state() == before  # Qualification is read-only.
    assert not filled_with(reference, 25, expected)
    for _ in range(5):
        allocate(reference, 254, 93)
    assert retained_fallback(reference, 25) is None  # Complete eviction is different.


def test_invalid_retained_payload_is_not_credited():
    reference = BypassReference(1)
    for _ in range(8):
        allocate(reference, 25, 99)
    allocate(reference, 254, 93)
    reference.cells[7]['payload_valid'] = 0  # Negative model fixture, not a DUT write.
    assert retained_fallback(reference, 25) is None


@pytest.mark.parametrize('initial_slot', (0, 2, 3, 4, 5, 6, 7))
def test_first_wrap_survivor_is_predicted_before_new_program_writes(initial_slot):
    reference = BypassReference(1)
    for _ in range(8 + initial_slot):
        allocate(reference, 25, 99)
    expected_slot = (reference.enq - 1) % 8
    for _ in range(1 if initial_slot == 0 else 9 - initial_slot):
        allocate(reference, 254, 93)
    witness = retained_fallback(reference, 25)
    assert witness is not None and witness['slot'] == expected_slot
    assert reference.cells[expected_slot]['tag'] == 99


@pytest.mark.parametrize('which', ('old', 'second'))
def test_installed_taken_self_loop_preserves_its_low_history_fixed_point(which):
    program = recipe(1)[which]
    history = program['conditional_history']
    cfi = (program['pc'] & ~7) + program['position']
    assert ((history << 2) ^ path_hash(cfi, program['pc'])) & MASK == history
    assert program['pc'] <= cfi  # Never pretend this metadata precedes pc-1.


@pytest.mark.parametrize('fault', (None, 'stale', 'pc', 'index_folds', 'tag_pc', 'tag_folds',
                                  'redirect_valid', 's2_override', 's3_override'))
def test_normal_return_qualification_uses_complete_input_context_only(fault):
    program = recipe(1)['old']
    history, pc = program['conditional_history'], program['pc']
    fs = folds(history)
    token = dict(source_tick=11, pc=pc, folds=(fold(history, 6, 6), fold(history, 12, 9)))
    boundary = dict(new_pc=pc, s1_folds=tuple(fs[i] for i in (1, 2, 7, 8)),
                    redirect_valid=0, s2_override=0, s3_override=0)
    if fault == 'stale': token['source_tick'] = 10
    elif fault == 'pc': token['pc'] ^= 64
    elif fault == 'index_folds': token['folds'] = (0, 0)
    elif fault == 'tag_pc': boundary['new_pc'] ^= 64
    elif fault == 'tag_folds': boundary['s1_folds'] = (0, 0, 0, 0)
    elif fault is not None: boundary[fault] = 1
    assert qualifies_return_request(token, boundary, pc=pc, history=history, after_tick=10) == (fault is None)


@pytest.mark.parametrize('fault', (None, 'hit', 'tableId', 'cfiPosition', 'takenCtr_value',
                                  'predTaken', 'readIndex', 'target', 'valid', 'extra_valid'))
def test_public_return_gate_compares_all_defined_payload_and_prediction_fields(fault):
    pc = recipe(1)['old']['pc']
    source = dict(valid=1, entries=[dict(hit=int(i == 2), position=6,
        attribute=dict(branchType=1)) for i in range(4)])
    payload = dict(data_valid=1, tag=99, position=6, counter=7)
    slots = [dict(valid=0) for _ in range(4)]
    slots[2] = dict(valid=1, hit=1, tableId=1, cfiPosition=6, takenCtr_value=7, predTaken=1)
    actual = dict(meta=dict(resolve=dict(utage=dict(readIndex=[25, 25], abtbResult=slots))),
                  prediction=dict(start_pc=pc, target=pc, taken=1, position=6))
    if fault == 'readIndex': actual['meta']['resolve']['utage']['readIndex'][1] ^= 1
    elif fault == 'target': actual['prediction']['target'] ^= 32
    elif fault == 'extra_valid': slots[0] = dict(slots[2])
    elif fault is not None: slots[2][fault] ^= 1
    expected, observed = public_readback_pair(actual, source, payload, pc=pc, index=25, position=6)
    board = Scoreboard('partial_wrap.public_return')
    if fault is None:
        board.check(expected=expected, actual=observed)
    else:
        with pytest.raises(ScoreboardMismatch):
            board.check(expected=expected, actual=observed)
