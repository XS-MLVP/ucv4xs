"""Pure expected-value checks; no DUT, timing, or observed prestate."""
from itertools import product
import pytest
from bpuverify.bpu.model.sc.model import NAMES
from bpuverify.bpu.model.sc.model import TABLES
from bpuverify.bpu.model.sc.model import ScReference
from bpuverify.bpu.model.sc.model import sc_requests
from bpuverify.bpu.model.sc.model import width
from bpuverify.bpu.model.sc.history import HistoryScReference
from bpuverify.bpu.model.sc.history import history_indices
from bpuverify.bpu.model.sc.history import history_requests


def transaction(bank=0, valid=1, ghr=0, bw=0, taken=0):
    pc = 0x40010000 + bank
    base = (pc >> 3) & 127
    return dict(pc=pc, resolve_meta=dict(commonHR=dict(valid=valid, ghr=ghr, bw=bw, imli=0),
        mbtb_entries=[[dict(rawHit=1, position=4), dict(rawHit=1, position=7)]],
        sc=dict(tagePredValid=[1, 1], useScPred=[0, 0], scPred=[1, 1], sumAboveThres=[0, 0],
            scBiasLowerBits=[0, 2], debug=dict(predPathIdx=[9], predImliIdx=base, predBiasIdx=base,
                predGlobalIdx=[base ^ (ghr & 127) ^ (ghr >> 7)], predBWIdx=[base ^ bw]))),
        branches=[dict(branch_type=1, position=4, taken=taken), dict(branch_type=1, position=7, taken=taken)])


@pytest.mark.parametrize('bank,ghr', tuple(product((0, 1), range(256))))
def test_all_GHR_bits_fold_to_the_physical_global_index(bank, ghr):
    tx = transaction(bank, ghr=ghr, bw=ghr % 16)
    expected = (ghr & 127) ^ (ghr // 128)
    assert history_indices(tx['pc'], tx['resolve_meta']['commonHR']) == dict(globalTable_0=expected, bwTable_0=ghr % 16)
    requests = history_requests(tx, ScReference().memories)
    assert requests[f'globalTable_0_bank{bank}']['set_index'] == expected
    assert requests[f'bwTable_0_bank{bank}']['set_index'] == ghr % 16


@pytest.mark.parametrize('bank,bw', tuple(product((0, 1), range(16))))
def test_all_BW_bits_select_the_expected_table_row(bank, bw):
    tx = transaction(bank, bw=bw)
    assert history_requests(tx, ScReference().memories)[f'bwTable_0_bank{bank}']['set_index'] == bw


@pytest.mark.parametrize('bank,valid,taken,signed', tuple(product((0, 1), (0, 1), (0, 1), range(-32, 32))))
def test_full_signed_saturation_and_unselected_lanes(bank, valid, taken, signed):
    tx, memories = transaction(bank, valid, taken=taken), ScReference().memories
    indices = dict(pathTable_0=9, globalTable_0=0, bwTable_0=0, imliTable=0, biasTable=0)
    for table, index in indices.items():
        name = f'{table}_bank{bank}'
        memories[name][index] = [signed & 63] * width(name)
    requests = history_requests(tx, memories)
    expected = min(31, max(-32, signed + (1 if taken else -1))) & 63
    changed = expected != (signed & 63)
    for table, index in indices.items():
        name = f'{table}_bank{bank}'
        enabled = bool(valid or table not in ('globalTable_0', 'bwTable_0'))
        assert (name in requests) == (enabled and changed)
        if name in requests:
            selected = (4, 10) if table == 'biasTable' else (1, 2)
            assert requests[name] == dict(set_index=index,
                masks=[int(way in selected) for way in range(width(name))],
                data=[expected if way in selected else signed & 63 for way in range(width(name))])


@pytest.mark.parametrize('bank,taken', tuple(product((0, 1), (0, 1))))
def test_invalid_common_history_preserves_the_admitted_legacy_requests(bank, taken):
    tx, memories = transaction(bank, valid=0, taken=taken), ScReference().memories
    assert history_requests(tx, memories) == sc_requests(tx, memories)
    with pytest.raises(ValueError, match='outside'):
        sc_requests(transaction(bank, valid=1, taken=taken), memories)


@pytest.mark.parametrize('field,value', (('valid', 2), ('ghr', -1), ('ghr', 256), ('bw', -1), ('bw', 16)))
def test_illegal_history_widths_are_rejected(field, value):
    tx = transaction()
    tx['resolve_meta']['commonHR'][field] = value
    with pytest.raises(ValueError):
        history_requests(tx, ScReference().memories)


@pytest.mark.parametrize('field', ('predGlobalIdx', 'predBWIdx'))
def test_captured_common_table_index_must_match_the_real_history(field):
    tx = transaction(ghr=0x91, bw=9)
    tx['resolve_meta']['sc']['debug'][field][0] ^= 1
    with pytest.raises(ValueError, match='disagrees'):
        history_requests(tx, ScReference().memories)


def test_valid_common_history_updates_are_pending_until_the_pipeline_slot():
    reference, tx = HistoryScReference(), transaction()
    expected = history_requests(tx, reference.memories)
    assert reference.accept(100, tx) == expected
    assert reference.pending == {102: expected}
    assert all(not slot['valid'] for name in NAMES for slot in reference.slots[name])
    with pytest.raises(ValueError, match='more than one'):
        reference.accept(100, tx)
