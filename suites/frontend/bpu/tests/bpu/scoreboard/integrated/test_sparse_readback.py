"""Sparse negative prediction: conditional metadata and final CFI differ."""
import pytest
from toffee import Scoreboard, ScoreboardMismatch

from suites.frontend.bpu.bpu.case.bypass.public_readback import public_readback_pair, training_tag_fold_pair
from suites.frontend.bpu.bpu.model.bypass.sparse import recipe
from suites.frontend.bpu.bpu.model.phr.model import folds


def fixture():
    program = recipe()['old']
    context = program['negative'][program['pc']]
    source = dict(valid=1, entries=[dict(hit=int(i == 2), position=6,
        attribute=dict(branchType=1)) for i in range(4)])
    slots = [dict(valid=0) for _ in range(4)]
    slots[2] = dict(valid=1, hit=1, tableId=1, cfiPosition=6, takenCtr_value=0, predTaken=0)
    actual = dict(meta=dict(resolve=dict(utage=dict(readIndex=list(context['indices']), abtbResult=slots,
        foldedPathHistForTrain_hist=[dict(foldedHist=f) for f in folds(context['tag_history'])]))),
        prediction=dict(start_pc=program['pc'], target=program['target'], taken=1, position=program['fallback']))
    return program, context, source, actual


@pytest.mark.parametrize('fault', (None, 'lower_index', 'upper_index', 'tableId', 'cfiPosition',
    'takenCtr_value', 'predTaken', 'hit', 'valid', 'target', 'position', 'taken', 'extra_valid'))
def test_negative_conditional_payload_and_taken_fallback_are_checked_independently(fault):
    program, context, source, actual = fixture()
    payload = dict(data_valid=1, tag=context['tags'][1], position=6, counter=0)
    slots = actual['meta']['resolve']['utage']['abtbResult']
    if fault == 'lower_index': actual['meta']['resolve']['utage']['readIndex'][0] ^= 1
    elif fault == 'upper_index': actual['meta']['resolve']['utage']['readIndex'][1] ^= 1
    elif fault == 'extra_valid': slots[0] = dict(slots[2])
    elif fault in ('target', 'position', 'taken'): actual['prediction'][fault] ^= 1
    elif fault is not None: slots[2][fault] ^= 1
    expected, observed = public_readback_pair(actual, source, payload,
        pc=program['pc'], target=program['target'], index=context['indices'], position=6,
        prediction_position=program['fallback'])
    board = Scoreboard('sparse.negative_return')
    if fault is None:
        board.check(expected=expected, actual=observed)
    else:
        with pytest.raises(ScoreboardMismatch):
            board.check(expected=expected, actual=observed)


@pytest.mark.parametrize('fault', (None, 1, 2, 7, 8, 'current_history'))
def test_public_training_folds_cannot_silently_change_stage(fault):
    program, context, source, actual = fixture()
    training = actual['meta']['resolve']['utage']['foldedPathHistForTrain_hist']
    if fault == 'current_history':
        for row, value in zip(training, folds(context['history']), strict=True):
            row['foldedHist'] = value
    elif fault is not None:
        training[fault]['foldedHist'] ^= 1
    expected, observed = training_tag_fold_pair(actual, context['tag_history'])
    board = Scoreboard('sparse.training_tag_ancestry')
    if fault is None:
        board.check(expected=expected, actual=observed)
    else:
        with pytest.raises(ScoreboardMismatch):
            board.check(expected=expected, actual=observed)
