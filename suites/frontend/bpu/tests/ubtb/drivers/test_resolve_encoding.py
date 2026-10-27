"""Resolve codec contracts; no architectural testcase manipulates pins."""
from dataclasses import replace

import pytest

from bpuverify.ubtb.agent.main import UbtbAgent
from bpuverify.ubtb.transaction.types import UbtbBatchTraining
from bpuverify.ubtb.transaction.types import UbtbBranchFeedback


BRANCH = UbtbBranchFeedback(0x80002460, 1, 7, 3, ras_action=1, mispredict=1)


def test_resolve_encoder_preserves_byte_addresses_attributes_and_masks():
    batch = UbtbBatchTraining(0x80001000, (None, BRANCH))
    actual = UbtbAgent._encode_resolve(batch, valid=1)
    assert actual['valid'] == 1
    assert actual['bits']['start_pc'] == batch.pc // 2
    assert len(actual['bits']['branches']) == 8
    assert actual['bits']['branches'][1] == {
        'valid': 1, 'target': BRANCH.target // 2, 'taken': 1, 'position': 7,
        'branch_type': 3, 'ras_action': 1, 'mispredict': 1,
    }
    for slot in (0, 2, 3, 4, 5, 6, 7):
        assert set(actual['bits']['branches'][slot].values()) == {0}


def test_resolve_encoder_ignores_invalid_mispredict_for_one_hot_validation():
    batch = UbtbBatchTraining(0x80001000, (replace(BRANCH, valid=0), BRANCH))
    assert UbtbAgent._encode_resolve(batch, valid=1)['bits']['branches'][0]['valid'] == 0


@pytest.mark.parametrize('batch, reason', [
    (UbtbBatchTraining(0, (BRANCH,) * 9), 'eight'),
    (UbtbBatchTraining(0, (BRANCH, BRANCH)), 'one valid misprediction'),
    (UbtbBatchTraining(0, (), fire=2), 'fire'),
    (UbtbBatchTraining(-1, ()), 'PC'),
    (UbtbBatchTraining(1 << 50, ()), 'PC'),
    *[(UbtbBatchTraining(0, (replace(BRANCH, **{field: value}),)), field)
      for field, value in (
          ('target', 1 << 50), ('position', 16), ('branch_type', 4),
          ('ras_action', 4), ('taken', 2), ('valid', 2), ('mispredict', 2),
      )],
])
def test_resolve_encoder_rejects_malformed_feedback(batch, reason):
    with pytest.raises(ValueError, match=reason):
        UbtbAgent._encode_resolve(batch, valid=1)


def test_resolve_idle_and_gate_disable_only_the_launch():
    batch = UbtbBatchTraining(0x80001000, (BRANCH,))
    idle = UbtbAgent._encode_resolve(batch, valid=0)
    gated = UbtbAgent._encode_resolve(replace(batch, fire=0), valid=1)
    assert idle == gated
    assert idle['valid'] == 0
    assert idle['bits']['branches'][0]['target'] == BRANCH.target // 2
    assert UbtbAgent._encode_resolve(None, valid=0)['bits']['start_pc'] == 0
