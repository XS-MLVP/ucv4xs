from copy import deepcopy
from itertools import product

import pytest

from bpuverify.bpu.model.sc.model import ScReference
from bpuverify.bpu.model.sc.model import encoded_payload
from bpuverify.bpu.model.sc.model import sc_requests
from tests.bpu.scoreboard.test_sc_masked_model import minimal_transaction
from bpuverify.bpu.model.sc.training_path import train_need_write
from bpuverify.bpu.model.sc.training_path import training_indices


@pytest.mark.parametrize('used,sc,tage,taken', tuple(product(range(2), repeat=4)))
def test_training_read_eligibility_truth_table(used, sc, tage, taken):
    tx = minimal_transaction(taken=taken)
    tx['resolve_meta']['sc'].update(useScPred=[used], scPred=[sc], tagePred=[tage])
    actual = train_need_write(encoded_payload(tx))
    # Both agreement conditions must hold to suppress a training read.
    suppressed = {(1, 0, 0, 0), (1, 1, 1, 1)}
    assert actual == int((used, sc, tage, taken) not in suppressed)


@pytest.mark.parametrize('missing', ('branch_valid', 'conditional', 'owner', 'provider'))
def test_training_read_rejects_missing_input_qualification(missing):
    bits = encoded_payload(minimal_transaction())
    bits['meta']['sc']['tagePred'] = [0]
    if missing == 'branch_valid':
        bits['branches'][0]['valid'] = 0
    elif missing == 'conditional':
        bits['branches'][0]['bits']['attribute']['branchType'] = 2
    elif missing == 'owner':
        bits['meta']['mbtb_entries'][0][0]['rawHit'] = 0
    else:
        bits['meta']['sc']['tagePredValid'][0] = 0
    saved = deepcopy(bits)
    assert train_need_write(bits) == 0
    assert bits == saved


@pytest.mark.parametrize('bank,taken', tuple(product(range(2), repeat=2)))
def test_saturated_counter_still_requires_training_read(bank, taken):
    tx, ref = minimal_transaction(bank=bank, taken=taken), ScReference()
    tx['resolve_meta']['sc']['tagePred'] = [0]
    for name, memory in ref.memories.items():
        selected = 4 if name.startswith('biasTable') else 1
        ways = 16 if name.startswith('biasTable') else 4
        memory[5] = [((31 if taken else 32) if way == selected else 0) for way in range(ways)]
    assert sc_requests(tx, ref.memories) == {}
    assert train_need_write(encoded_payload(tx)) == 1


@pytest.mark.parametrize('pc,path,common,expected', (
    (0x40000800, 0, dict(ghr=0, bw=0, imli=0), (0, 0, 0, 0, 0)),
    (0x40000809, 2, dict(ghr=128, bw=15, imli=255), (3, 0, 14, 127, 1)),
    (0x40000bf8, 127, dict(ghr=255, bw=15, imli=128), (0, 1, 112, 126, 127)),
))
def test_training_hash_hand_vectors(pc, path, common, expected):
    assert tuple(training_indices(pc, path, common).values()) == expected

