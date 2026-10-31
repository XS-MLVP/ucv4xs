"""Bounded byte encoding and atomic validation before concurrent launches."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.ubtb.agent.main import UbtbAgent
from suites.frontend.bpu.ubtb.driver.encoding import _encode_lookup, _encode_training, _encode_resolve
from suites.frontend.bpu.ubtb.transaction.types import PredictRequest, BranchTraining, UbtbBatchTraining, UbtbBranchFeedback


GOOD = BranchTraining(0x80001002, 0x80402342, 1, 3, 2)


@pytest.mark.parametrize('bad', (-2, 1, 0x80001001, 1 << 50, True, 1.5, '0'))
def test_lookup_rejects_non_byte_domain_before_drive(bad):
    with pytest.raises(ValueError):
        _encode_lookup(PredictRequest(bad), valid=1)


@pytest.mark.parametrize('field', ('pc', 'target'))
@pytest.mark.parametrize('bad', (-2, 1, 1 << 50, True, 1.5))
def test_both_training_sources_validate_the_full_byte_address(field, bad):
    with pytest.raises(ValueError):
        _encode_training(replace(GOOD, **{field: bad}), valid=1)
    branch = UbtbBranchFeedback(GOOD.target, 1, 3, 2, mispredict=1)
    batch = UbtbBatchTraining(GOOD.pc, (branch,))
    batch = replace(batch, pc=bad) if field == 'pc' else replace(batch, branches=(replace(branch, target=bad),))
    with pytest.raises(ValueError):
        _encode_resolve(batch, valid=1)


def test_byte_width_is_not_mistaken_for_raw_pruned_port_width():
    maximum = (1 << 50) - 2
    fast = _encode_training(replace(GOOD, pc=maximum, target=maximum), valid=1)['bits']
    assert fast['start_pc'] == fast['branch']['target'] == (1 << 49) - 1
    assert _encode_lookup(PredictRequest(maximum), valid=1)['start_pc'] == (1 << 49) - 1
    branch = UbtbBranchFeedback(maximum, 1, 3, 2, mispredict=1)
    resolve = _encode_resolve(UbtbBatchTraining(maximum, (branch,)), valid=1)['bits']
    assert resolve['start_pc'] == resolve['branches'][0]['target'] == (1 << 49) - 1


def fake_agent():
    calls = []
    return SimpleNamespace(_require_started=lambda: None,
        _encode_training=_encode_training, _encode_resolve=_encode_resolve,
        resolve_driver=SimpleNamespace(send=lambda tx: calls.append(('resolve', tx))),
        training_driver=SimpleNamespace(send=lambda tx: calls.append(('fast', tx)))), calls


async def test_bad_fast_source_does_not_launch_the_other_concurrent_source():
    agent, calls = fake_agent()
    good = UbtbBatchTraining(GOOD.pc, (UbtbBranchFeedback(GOOD.target, 1, 3, 2, mispredict=1),))
    with pytest.raises(ValueError):
        await UbtbAgent.train_resolve(agent, good, fast_train=replace(GOOD, target=GOOD.target | 1))
    assert calls == []


async def test_malformed_later_burst_item_does_not_partially_launch_earlier_items():
    agent, calls = fake_agent()
    with pytest.raises(ValueError):
        await UbtbAgent.train_contiguous(agent, (GOOD, replace(GOOD, pc=GOOD.pc | 1)))
    assert calls == []
