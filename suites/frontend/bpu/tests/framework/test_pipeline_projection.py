"""Autonomous expectations survive the actual ABI without invented echo fields."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.pipeline import compared_values, main_metadata_values
from suites.frontend.bpu.bpu.model.projection import INTEGRATED_PIPELINE, ABSTRACT_PIPELINE
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from tests.bpu.scoreboard.test_pipeline_checking import ready_checker, fixture_row

pytestmark = pytest.mark.selftest


def physical_row(checker, events):
    row = fixture_row(checker, events)
    row['inputs']['metadata_ready'] = True
    return row


def physical_checker():
    checker, events = ready_checker()
    checker.projection = INTEGRATED_PIPELINE
    return checker, events


def test_public_target_absence_does_not_remove_independent_internal_target_comparisons():
    checker, events = physical_checker()
    row = physical_row(checker, events)
    cycle = checker.model.evaluate(events)
    expected, actual, _ = compared_values(checker.model, cycle, row['observed'], events,
                                         projection=INTEGRATED_PIPELINE)
    checker.board.check(expected=expected, actual=actual)
    assert 'target' not in expected['prediction']
    assert 'pc' not in expected['metadata']
    assert set(expected['metadata']['history']['phrPtr']) == {'value'}
    assert all('target' in expected[f'choice{stage}'] for stage in (1, 2, 3))
    assert 'flag' in ABSTRACT_PIPELINE.history(cycle.metadata.history)['phrPtr']


@pytest.mark.parametrize('fault', ('internal-target', 'missing-public-pc', 'fake-public-target', 'low-bits', 'fake-flag'))
def test_wrong_retained_fields_or_fabricated_echo_cannot_pass_by_using_dce_projection(fault):
    checker, events = physical_checker()
    row = physical_row(checker, events)
    before = deepcopy(checker.model.state())
    if fault == 'internal-target':
        row['observed']['choices'][0]['target'] ^= 2
    elif fault == 'missing-public-pc':
        del row['observed']['prediction']['pc']
    elif fault == 'fake-public-target':
        row['observed']['prediction']['target'] = 0
    elif fault == 'low-bits':
        row['observed']['metadata']['history']['phrLowBits'] ^= 1
    else:
        row['observed']['metadata']['history']['phrPtr']['flag'] = 0
    checker.capture(row, NS(tick=102))
    with pytest.raises((AssertionError, KeyError, ValueError)) as first:
        checker.raise_failure()
    assert checker.model.state() == before
    with pytest.raises(type(first.value)) as last:
        checker.finish()
    assert last.value is first.value


def source_receipt(checker):
    token = next(iter(checker.model.published.values()))
    source = NS(prediction_tick=10, meta_tick=14,
        prediction=NS(start_pc=token.pc, target=None, taken=int(token.early.branch.taken),
                      position=token.early.branch.position, s2_override=0, s3_override=0),
        meta=NS(perf=None, redirect=dict(phr=INTEGRATED_PIPELINE.history(token.history)), resolve={}))
    checker.s1_accepts[token.sequence] = 10
    checker.source_receipts[14] = token
    return token, source


def test_physical_source_and_redirect_keep_the_preexisting_exact_input_owner_without_perf():
    checker, _ = physical_checker()
    token, source = source_receipt(checker)
    assert checker.source_token(source) is token
    request = BpuRedirect(token.pc, source.meta.redirect)
    checker.plan_redirect(source, request)
    actual = dict(pc=token.pc, target=token.pc, taken=1, kind=2, action=0,
                  history=INTEGRATED_PIPELINE.history(token.history))
    assert checker._accepted_redirect_origin(actual, NS(tick=104)) is token


@pytest.mark.parametrize('fault', ('fake-perf', 'fake-target', 'wrong-input-tick', 'unknown-output-tick'))
def test_equal_payload_or_synthesized_perf_is_not_a_source_identity(fault):
    checker, _ = physical_checker()
    token, source = source_receipt(checker)
    if fault == 'fake-perf':
        source.meta.perf = NS(start_pc=token.pc)
    elif fault == 'fake-target':
        source.prediction.target = token.early.branch.target
    elif fault == 'wrong-input-tick':
        source.prediction_tick += 2
    else:
        source.meta_tick += 2
    with pytest.raises(AssertionError):
        checker.source_token(source)


def test_physical_finish_does_not_erase_accepted_pipeline_work():
    checker, events = physical_checker()
    checker.counts['metadata'] = 1
    with pytest.raises(AssertionError, match='undrained'):
        checker.finish()
    for tick in (102, 104, 106):
        checker.capture(physical_row(checker, events), NS(tick=tick))
        checker.raise_failure()
    checker.finish()
