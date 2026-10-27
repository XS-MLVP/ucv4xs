"""A correct hit port cannot hide broken metadata sent back into training."""
from copy import deepcopy

import pytest
from toffee import ScoreboardMismatch

from bpuverify.utage.case.useful_address_scenario import UsefulContext
from bpuverify.utage.model.addressing import FOLD_LAYOUT, fold_history
from bpuverify.utage.model.split_context import contexts
from bpuverify.utage.transaction.types import UtagePrediction


@pytest.mark.parametrize('fault', (None, 'lower_index', 'upper_index', 'meta_hit', 'tableId',
    'takenCtr_value', 'predTaken', 'baseTaken', 'baseIsStrongBias', 'valid', 'extra_valid', 'position',
    'port_hit', 'port_taken', *range(19)))
async def test_complete_split_context_metadata_is_checked_before_it_can_be_reused(fault, tmp_path):
    profile = contexts()['positive']
    entries = [dict(valid=int(i == 0), hit=int(i == 0), tableId=0, takenCtr_value=4,
        predTaken=1, baseTaken=0, baseIsStrongBias=0, cfiPosition=6 + i) for i in range(4)]
    meta = dict(readIndex=list(profile.indices), abtbResult=entries,
        foldedPathHistForTrain_hist=[dict(foldedHist=fold_history(profile.tag_history, length, width))
                                    for length, width in FOLD_LAYOUT])
    hit, taken = 1, 1
    if fault == 'lower_index': meta['readIndex'][0] ^= 1
    elif fault == 'upper_index': meta['readIndex'][1] ^= 1
    elif fault == 'meta_hit': entries[0]['hit'] ^= 1
    elif fault == 'extra_valid': entries[1]['valid'] = 1
    elif fault == 'position': entries[0]['cfiPosition'] ^= 1
    elif fault == 'port_hit': hit ^= 1
    elif fault == 'port_taken': taken ^= 1
    elif isinstance(fault, int): meta['foldedPathHistForTrain_hist'][fault]['foldedHist'] ^= 1
    elif fault is not None: entries[0][fault] ^= 1
    prediction = UtagePrediction(hit, taken, meta)
    before = deepcopy(meta)
    calls = []
    class Agent:
        async def predict(self, pc, position, base, **kwargs):
            calls.append(dict(pc=pc, position=position, base=base, **kwargs))
            return prediction
    run = UsefulContext(Agent(), mode='adjacent', name='split-negative-control',
                        index=profile.indices[0], output=tmp_path)
    async def check():
        return await run.predict(profile.pc, profile.tag_history, 0, position=6, expected=(1, 0, 4, 1),
            index_pc=profile.index_pc, index_history=profile.index_history)
    if fault is None:
        assert await check() is prediction
        assert len(run.predictions) == 1
    else:
        with pytest.raises(ScoreboardMismatch):
            await check()
        assert not run.predictions
    assert not run.operations
    assert meta == before
    assert calls == [dict(pc=profile.pc, position=6, base=0, folded_history=profile.tag_history,
                         index_pc=profile.index_pc, index_history=profile.index_history)]
