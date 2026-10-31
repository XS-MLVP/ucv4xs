"""Only proven missing repair may use INT-013's known-defect classification."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.checker.target_repair import MissingMicroFullTargetRepair, check_micro_target_repair
from suites.frontend.bpu.bpu.transaction.types import BpuMeta, BpuPerf, BpuPrediction, BpuStage1Source, BpuTransaction
from tests.bpu.testcase.test_target_boundary import test_early_partial_target_wrap_is_eventually_corrected as hardware_case


PC, TARGET, WRAPPED, POSITION = 0x407F_FFE0, 0x4080_0100, 0x4040_0100, 4


def original(target=WRAPPED):
    prediction = BpuPrediction(PC, target, 1, POSITION, 0, 0)
    perf = BpuPerf(PC, target, 1, POSITION, BpuStage1Source.UBTB)
    return BpuTransaction(10, 14, prediction, BpuMeta({}, {}, perf))


def repair():
    return BpuPrediction(PC, TARGET, 1, POSITION, 0, 1)


def check(transaction, repairs):
    return check_micro_target_repair(transaction, repairs, pc=PC, target=TARGET, position=POSITION)


def test_only_established_wrap_without_causal_repair_has_known_defect_type():
    with pytest.raises(MissingMicroFullTargetRepair, match='causal_window'):
        check(original(), ())
    mark = next(mark for mark in hardware_case.pytestmark if mark.name == 'xfail')
    assert mark.kwargs['strict'] is True
    assert mark.kwargs['raises'] is MissingMicroFullTargetRepair


@pytest.mark.parametrize('fault', (
    'wrong-pc', 'wrong-position', 'not-taken', 'override', 'wrong-source',
    'wrong-echo', 'unexpected-target', 'invalid-window',
))
def test_bad_antecedent_is_an_ordinary_failure_even_if_repair_is_missing(fault):
    transaction = original()
    prediction, meta = transaction.prediction, transaction.meta
    if fault == 'wrong-pc':
        prediction = replace(prediction, start_pc=PC + 8)
    elif fault == 'wrong-position':
        prediction = replace(prediction, position=POSITION + 1)
    elif fault == 'not-taken':
        prediction = replace(prediction, taken=0)
    elif fault == 'override':
        prediction = replace(prediction, s2_override=1)
    elif fault == 'wrong-source':
        meta = replace(meta, perf=replace(meta.perf, s1_source=BpuStage1Source.ABTB))
    elif fault == 'wrong-echo':
        meta = replace(meta, perf=replace(meta.perf, s1_target=TARGET))
    elif fault == 'unexpected-target':
        transaction = original(TARGET + 2)
        prediction, meta = transaction.prediction, transaction.meta
    elif fault == 'invalid-window':
        transaction = replace(transaction, meta_tick=transaction.prediction_tick)
    transaction = replace(transaction, prediction=prediction, meta=meta)
    with pytest.raises(AssertionError) as caught:
        check(transaction, ())
    assert not isinstance(caught.value, MissingMicroFullTargetRepair)


@pytest.mark.parametrize('stage', ('s2', 's3'))
def test_a_complete_correct_causal_repair_satisfies_the_requirement(stage):
    prediction = replace(repair(), s2_override=int(stage == 's2'), s3_override=int(stage == 's3'))
    check(original(), ((12 if stage == 's2' else 14, prediction),))


@pytest.mark.parametrize('fault', (
    'wrong-pc', 'wrong-target', 'not-taken', 'wrong-position', 'no-stage',
    'two-stages', 'too-early', 'too-late', 'duplicate',
))
def test_wrong_extra_or_misassociated_repairs_are_not_a_known_missing_repair(fault):
    prediction, tick = repair(), 14
    if fault == 'wrong-pc':
        prediction = replace(prediction, start_pc=PC + 8)
    elif fault == 'wrong-target':
        prediction = replace(prediction, target=TARGET + 2)
    elif fault == 'not-taken':
        prediction = replace(prediction, taken=0)
    elif fault == 'wrong-position':
        prediction = replace(prediction, position=POSITION + 1)
    elif fault == 'no-stage':
        prediction = replace(prediction, s3_override=0)
    elif fault == 'two-stages':
        prediction = replace(prediction, s2_override=1)
    elif fault == 'too-early':
        tick = 10
    elif fault == 'too-late':
        tick = 16
    repairs = ((tick, prediction),) * (2 if fault == 'duplicate' else 1)
    with pytest.raises(AssertionError) as caught:
        check(original(), repairs)
    assert not isinstance(caught.value, MissingMicroFullTargetRepair)


def test_an_upstream_target_fix_is_allowed_but_does_not_authorize_extra_repairs():
    check(original(TARGET), ())
    with pytest.raises(AssertionError) as caught:
        check(original(TARGET), ((14, repair()),))
    assert not isinstance(caught.value, MissingMicroFullTargetRepair)
