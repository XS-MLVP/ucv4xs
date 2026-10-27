"""Pure independent partial-wrap model and failure handoff contracts."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch
from bpuverify.utage.checker.partial_wrap import UtagePartialWrapChecker
from bpuverify.utage.model.partial_wrap import UtagePartialWrapReference
from tests.utage.scoreboard.test_useful_model import payload


def cells():
    return [dict(valid=1, index=index, data_valid=1, tag=index,
        position=5, counter=3) for index in range(8)]


@pytest.mark.parametrize('gap', (2, 8, 24))
def test_two_writes_forward_counter_keep_six_neighbors_and_obey_latency(gap):
    reference = UtagePartialWrapReference(cells())
    request = payload(index=0, increase=True)
    for tick in range(0, gap + 10, 2):
        reference.advance(tick, request if tick in (0, gap) else None)
        completed = int(tick >= 6) + int(tick >= gap + 6)
        expected = cells()
        for slot in range(completed): expected[slot] = dict(expected[0], counter=2 - slot)
        assert reference.cells == expected
        assert (reference.enq, reference.mask) == (completed, 255 if completed == 0 else (1 << completed) - 1)
    assert reference.pending == 0 and reference.accepted == 2


@pytest.mark.parametrize('kind', ('missing-cell', 'duplicate-index', 'bad-counter', 'invalid-cell', 'too-wide-tag'))
def test_initial_scope_is_validated(kind):
    expected = cells()
    if kind == 'missing-cell': expected.pop()
    elif kind == 'duplicate-index': expected[-1]['index'] = 0
    elif kind == 'bad-counter': expected[2]['counter'] = 7
    elif kind == 'invalid-cell': expected[3]['valid'] = 0
    elif kind == 'too-wide-tag': expected[4]['tag'] = 256
    with pytest.raises(ValueError): UtagePartialWrapReference(expected)


@pytest.mark.parametrize('kind', ('wrong-provider', 'incorrect-direction', 'unknown-index', 'wrong-position'))
def test_feedback_scope_rejected_before_clock_state_changes(kind):
    reference = UtagePartialWrapReference(cells())
    request = payload(index=0)
    if kind == 'wrong-provider': request['meta']['abtbResult'][0]['tableId'] = 0
    elif kind == 'incorrect-direction': request['branch']['taken'] = 1
    elif kind == 'unknown-index': request['meta']['readIndex'][1] = 20
    elif kind == 'wrong-position': request['branch']['position'] = 6
    with pytest.raises(ValueError): reference.advance(0, request)
    assert reference.last_tick is None and reference.pending == 0 and reference.cells == cells()


def test_comparison_failure_is_latched_once_and_raised_in_foreground():
    checker = UtagePartialWrapChecker(cells(), bank=0, mode='adjacent')
    wrong = deepcopy(cells())
    wrong[7]['counter'] = 0
    row = dict(public=dict(valid=0, bits=None), cells=wrong, enq=0, mask=255,
        hits=(0,) * 8, chosen_first=0, response={})
    checker.capture(SimpleNamespace(event=SimpleNamespace(tick=20), value=row))
    failure = checker._failure
    assert isinstance(failure, ScoreboardMismatch)
    checker.capture(SimpleNamespace(event=SimpleNamespace(tick=22), value=row))
    assert checker._failure is failure and checker.scoreboard.status.failed == 1
    with pytest.raises(ScoreboardMismatch) as observed: checker.finish()
    assert observed.value is failure
    assert all(text in str(failure) for text in ('all retained and updated shadow cells', 'observed_tick: 20', 'status:'))

