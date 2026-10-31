"""Byte-domain requirements checked against literal halfword-port values."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.ubtb.driver.encoding import _encode_training, _encode_resolve
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents, UbtbReference
from suites.frontend.bpu.ubtb.monitor.decode import _decode_prediction_sample
from suites.frontend.bpu.ubtb.monitor.semantic import decode_events
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining, PredictRequest, UbtbBatchTraining, UbtbBranchFeedback


FEEDBACK = BranchTraining(0x80001002, 0x80402342, 1, 3, 2)


def signal(value):
    return NS(as_int=lambda: value)


def test_fast_codec_uses_literal_halfword_values_not_byte_numbers():
    actual = _encode_training(FEEDBACK, valid=1)['bits']
    assert actual['start_pc'] == 0x40000801
    assert actual['branch']['target'] == 0x402011A1


def test_resolve_codec_uses_the_same_literal_domain_and_keeps_slot_identity():
    branch = UbtbBranchFeedback(FEEDBACK.target, 1, 3, 2, mispredict=1)
    actual = _encode_resolve(UbtbBatchTraining(FEEDBACK.pc, (None, branch)), valid=1)['bits']
    assert actual['start_pc'] == 0x40000801
    assert actual['branches'][1]['target'] == 0x402011A1
    assert actual['branches'][0]['valid'] == 0


def test_prediction_monitor_expands_literal_halfword_output():
    sample = NS(valid=signal(1), enabled=signal(1), bits=NS(taken=signal(1), target_addr=signal(0x402011A1),
        cfiPosition=signal(3), attribute=NS(branchType=signal(2), rasAction=signal(0))))
    assert _decode_prediction_sample(sample).target == 0x80402342


def test_prediction_monitor_treats_disabled_taken_hit_as_no_prediction():
    sample = NS(valid=signal(1), enabled=signal(0), bits=NS(taken=signal(1), target_addr=signal(0x402011A1),
        cfiPosition=signal(3), attribute=NS(branchType=signal(2), rasAction=signal(0))))
    assert _decode_prediction_sample(sample).valid == 0


def test_input_monitor_expands_lookup_and_both_feedback_sources():
    branch = NS(**{name: signal(value) for name,value in dict(
        target=0x402011A1, taken=1, position=3, branch_type=2, ras_action=0, mispredict=1, valid=1).items()})
    sample = NS(lookup=NS(start_pc=signal(0x40000801), s0_fire=signal(1), s1_fire=signal(1)),
        fast_valid=signal(1), fast=NS(start_pc=signal(0x40000801), branch=branch),
        resolve_valid=signal(1), resolve=NS(start_pc=signal(0x40000801), branches=(branch,)),
        enabled=signal(1), reset=signal(0))
    event = decode_events(sample)
    assert event.predict.pc == FEEDBACK.pc
    assert event.fast_feedback == FEEDBACK
    assert event.resolve_feedback.pc == FEEDBACK.pc
    assert event.resolve_feedback.branches[0].target == FEEDBACK.target


def learn_and_predict(feedback):
    model = UbtbReference()
    model.advance(UbtbEvents(fast_feedback=feedback))
    model.advance(UbtbEvents())
    return model.advance(UbtbEvents(predict=PredictRequest(feedback.pc)))


def test_byte_target_bit22_is_a_real_stored_offset_not_a_region_bit():
    assert learn_and_predict(FEEDBACK).target == FEEDBACK.target


@pytest.mark.parametrize('pc,target,expected', (
    (0x807FFFE0, 0x80800100, 0x80000100),
    (0x80800000, 0x807FFF00, 0x80FFFF00),
))
def test_byte_target_wrap_is_at_eight_mib_and_uses_original_pc_region(pc, target, expected):
    assert learn_and_predict(replace(FEEDBACK, pc=pc, target=target)).target == expected


def test_unguarded_byte_domain_includes_the_upper_half_of_50_bit_space():
    feedback = replace(FEEDBACK, pc=(1 << 50) - 0x1000, target=(1 << 50) - 2)
    assert learn_and_predict(feedback).target == feedback.target


@pytest.mark.parametrize('field', ('pc', 'target'))
def test_unaligned_byte_inputs_are_rejected_instead_of_silently_reinterpreted(field):
    feedback = replace(FEEDBACK, **{field: getattr(FEEDBACK, field) | 1})
    with pytest.raises(ValueError):
        _encode_training(feedback, valid=1)
    with pytest.raises(ValueError):
        learn_and_predict(feedback)
