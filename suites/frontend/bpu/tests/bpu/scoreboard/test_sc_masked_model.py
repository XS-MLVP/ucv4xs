from bpuverify.common.model.configuration import *
from copy import deepcopy
from itertools import product
import pytest
from bpuverify.bpu.model.sc.model import advance
from bpuverify.bpu.model.sc.model import encoded_payload
from bpuverify.bpu.model.sc.model import sc_requests
from bpuverify.bpu.model.sc.model import ScReference
from bpuverify.bpu.model.sc.model import width
from bpuverify.bpu.model.sc.model import zero_slots

MASK_CASES = [(ways, a, b, dirty, ready) for ways in (SC_WAYS, 4 * SC_WAYS)
              for a, b, dirty, ready in product(range(ways), range(ways), (0, 1), (0, 1))]


@pytest.mark.parametrize('ways,old_way,new_way,dirty,ready', MASK_CASES)
def test_mask_merge_preserves_full_state_and_write_wins_drain(ways, old_way, new_way, dirty, ready):
    slots = zero_slots(ways)
    old_payload = dict(set_index=7, masks=[int(index == old_way) for index in range(ways)],
                       data=[9 if index == old_way else 0 for index in range(ways)])
    slots[0] = dict(valid=1, dirty=dirty, payload=deepcopy(old_payload))
    write = dict(set_index=7, masks=[int(index == new_way) for index in range(ways)],
                 data=[17 if index == new_way else 0 for index in range(ways)])
    saved, saved_write = deepcopy(slots), deepcopy(write)
    actual, drain, action = advance(slots, ready=ready, write=write)
    expected = deepcopy(saved)
    expected[0] = dict(valid=1, dirty=1, payload=dict(set_index=7,
        masks=[int(index in (old_way, new_way)) for index in range(ways)],
        data=[17 if index == new_way else 9 if index == old_way else 0 for index in range(ways)]))
    assert actual == expected
    assert drain == (old_payload if dirty and ready else None)
    assert action == ('dirty_merge' if dirty else 'clean_reactivate')
    assert slots == saved and write == saved_write


def minimal_transaction(bank=0, taken=0):
    return dict(pc=0x40000800 + bank, resolve_meta=dict(commonHR=dict(valid=0),
        mbtb_entries=[[dict(rawHit=1, position=4)]],
        sc=dict(tagePredValid=[1], useScPred=[0], scPred=[1 - taken], sumAboveThres=[0],
                scBiasLowerBits=[0], debug=dict(predPathIdx=[5, 5], predImliIdx=5, predBiasIdx=5))),
        branches=[dict(position=4, target=0x40000a00, branch_type=1, taken=taken,
                       mispredict=0, ras_action=0)])


@pytest.mark.parametrize('bank,bits,taken', tuple(product(range(2), range(64), range(2))))
def test_accepted_feedback_derives_signed_saturating_full_payloads(bank, bits, taken):
    ref, tx = ScReference(), minimal_transaction(bank, taken)
    for table in ('pathTable_0', 'pathTable_1', 'imliTable', 'biasTable'):
        name, selected = f'{table}_bank{bank}', 16 if table == 'biasTable' else 4
        ref.memories[name][5] = [bits if index == selected else 0 for index in range(width(name))]
    saved = deepcopy(ref.memories)
    actual = sc_requests(tx, ref.memories)
    signed = bits - 64 if bits >= 32 else bits
    wanted = max(-32, min(31, signed + (1 if taken else -1))) & 63
    if wanted == bits:
        assert actual == {}
    else:
        assert len(actual) == 4
        for table in ('pathTable_0', 'pathTable_1', 'imliTable', 'biasTable'):
            name, selected = f'{table}_bank{bank}', 16 if table == 'biasTable' else 4
            assert actual[name] == dict(set_index=5,
                masks=[int(index == selected) for index in range(width(name))],
                data=[wanted if index == selected else 0 for index in range(width(name))])
    assert ref.memories == saved


@pytest.mark.parametrize('kind', ('common_hr', 'owner', 'provider', 'sc_used', 'nonconditional'))
def test_reference_rejects_unqualified_metadata(kind):
    tx, ref = minimal_transaction(), ScReference()
    if kind == 'common_hr':
        tx['resolve_meta']['commonHR']['valid'] = 1
    elif kind == 'owner':
        tx['resolve_meta']['mbtb_entries'][0][0]['rawHit'] = 0
    elif kind == 'provider':
        tx['resolve_meta']['sc']['tagePredValid'][0] = 0
    elif kind == 'sc_used':
        tx['resolve_meta']['sc']['useScPred'][0] = 1
    else:
        tx['branches'][0]['branch_type'] = 2
    with pytest.raises(ValueError):
        sc_requests(tx, ref.memories)


@pytest.mark.parametrize('ways', (SC_WAYS, 4 * SC_WAYS))
def test_full_dirty_overwrite_explicitly_rejected(ways):
    slots = zero_slots(ways)
    for index, entry in enumerate(slots):
        entry.update(valid=1, dirty=1)
        entry['payload']['set_index'] = index
    with pytest.raises(ValueError, match='full dirty overwrite'):
        advance(slots, ready=1, write=dict(set_index=9, masks=[1] * ways, data=[0] * ways))


def test_public_payload_padding_and_reference_reset_do_not_alias_inputs():
    tx = minimal_transaction()
    payload = encoded_payload(tx)
    assert len(payload['branches']) == 8
    assert [row['valid'] for row in payload['branches']] == [1] + [0] * 7
    payload['meta']['sc']['scPred'][0] ^= 1
    assert payload['meta'] != tx['resolve_meta']
    ref = ScReference()
    ref.accept(8, tx)
    assert set(ref.pending) == {10}
    ref.reset()
    assert not ref.pending and all(not value for value in ref.memories.values())
    assert all(slots == zero_slots(width(name)) for name, slots in ref.slots.items())

