"""Hand-derived target/counter paths and metadata mismatch controls."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch
from suites.frontend.bpu.bpu.checker.ittage import check_metadata
from suites.frontend.bpu.bpu.model.ittage import Entry, IttageContextModel


def context():
    model = IttageContextModel()
    for table, target in enumerate((100, 200, 300)):
        model.advance(dict(valid=1, bits=table), target, mispredict=True)
    assert model.entries == {0: Entry(100, 1), 1: Entry(200, 1), 2: Entry(300, 2)}
    return model


def test_confidence_zero_changes_target_and_penalizes_the_actual_alternate():
    model, operations = context(), set()
    for target in (300, 300, 200, 200, 200, 200, 200, 100, 100, 100):
        operations.update(model.advance(dict(valid=0), target, mispredict=model.target() != target))
    assert model.entries == {0: Entry(100, 1), 1: Entry(100, 0), 2: Entry(100, 1, 1)}
    assert model.target() == 100
    assert operations >= {'high_hold', 'decrement', 'low_hold', 'increment',
                          'alternate_selected', 'alternate_penalty', 'zero_confidence_target_write'}


@pytest.mark.parametrize('field', ('providerCnt_value', 'providerTarget_addr',
                                  'providerUsefulCnt_value', 'altProviderCnt_value', 'altProviderTarget_addr'))
def test_corrupt_public_metadata_raises_with_phase_and_expected_state(field):
    model = context()
    actual = deepcopy(model.metadata())
    actual[field] ^= 1
    transaction = SimpleNamespace(meta_tick=42, prediction=SimpleNamespace(start_pc=16),
                                  meta=SimpleNamespace(resolve=dict(ittage=actual)))
    with pytest.raises(ScoreboardMismatch, match='feedback-fault'):
        check_metadata(Scoreboard('ittage'), model, transaction, phase='feedback-fault')


@pytest.mark.parametrize('proposal', ({'valid':1,'bits':0}, {'valid':1,'bits':3}, {'valid':1,'bits':True}))
def test_reject_non_longer_or_out_of_geometry_allocation(proposal):
    model = context()
    before = dict(model.entries)
    with pytest.raises(ValueError, match='allocation proposal'):
        model.advance(proposal, 400, mispredict=True)
    assert model.entries == before
