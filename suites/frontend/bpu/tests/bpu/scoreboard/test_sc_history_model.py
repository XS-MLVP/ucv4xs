"""Pure expected-value checks; no DUT, timing, or observed prestate."""
from suites.frontend.bpu.models.configuration import *
from itertools import product
import pytest
from suites.frontend.bpu.bpu.model.sc.model import NAMES
from suites.frontend.bpu.bpu.model.sc.model import TABLES
from suites.frontend.bpu.bpu.model.sc.model import ScReference
from suites.frontend.bpu.bpu.model.sc.model import sc_requests
from suites.frontend.bpu.bpu.model.sc.model import width
from suites.frontend.bpu.bpu.model.sc.history import HistoryScReference
from suites.frontend.bpu.bpu.model.sc.history import history_indices
from suites.frontend.bpu.bpu.model.sc.history import history_requests


def transaction(bank=0, valid=1, ghr=0, bw=0, taken=0):
    pc = 0x40010000 + bank
    base = (pc // ALIGN_HALFWORDS) & 127
    return dict(pc=pc, resolve_meta=dict(commonHR=dict(valid=valid, ghr=ghr, bw=bw, imli=0),
        mbtb_entries=[[dict(rawHit=1, position=4), dict(rawHit=1, position=7)]],
        sc=dict(tagePredValid=[1, 1], useScPred=[0, 0], scPred=[1, 1], sumAboveThres=[0, 0],
            scBiasLowerBits=[0, 2], debug=dict(predPathIdx=[9, 37], predImliIdx=base, predBiasIdx=base,
                predGlobalIdx=[base ^ (ghr & 127) ^ ((ghr >> 7) & 1), base ^ (ghr & 127) ^ ((ghr >> 7) & 127) ^ (ghr >> 14)], predBWIdx=[base ^ (bw & 15), base ^ (bw & 127) ^ (bw >> 7)]))),
        branches=[dict(branch_type=1, position=4, taken=taken), dict(branch_type=1, position=7, taken=taken)])


@pytest.mark.parametrize('bank,ghr', tuple(product((0, 1), range(256))))
def test_all_GHR_bits_fold_to_the_physical_global_index(bank, ghr):
    tx = transaction(bank, ghr=ghr, bw=ghr % 16)
    expected = (ghr & 127) ^ (ghr // 128)
    assert history_indices(tx['pc'], tx['resolve_meta']['commonHR']) == dict(globalTable_0=expected, globalTable_1=expected, bwTable_0=ghr % 16, bwTable_1=ghr % 16)
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
    indices = dict(pathTable_0=9, pathTable_1=37, globalTable_0=0, globalTable_1=0, bwTable_0=0, bwTable_1=0, imliTable=0, biasTable=0)
    for table, index in indices.items():
        name = f'{table}_bank{bank}'
        memories[name][index] = [signed & 63] * width(name)
    requests = history_requests(tx, memories)
    expected = min(31, max(-32, signed + (1 if taken else -1))) & 63
    changed = expected != (signed & 63)
    for table, index in indices.items():
        name = f'{table}_bank{bank}'
        enabled = bool(valid or table not in ('globalTable_0', 'globalTable_1', 'bwTable_0', 'bwTable_1'))
        assert (name in requests) == (enabled and changed)
        if name in requests:
            selected = (16, 30) if table == 'biasTable' else (4, 7)
            assert requests[name] == dict(set_index=index,
                masks=[int(way in selected) for way in range(width(name))],
                data=[expected if way in selected else signed & 63 for way in range(width(name))])


@pytest.mark.parametrize('bank,taken', tuple(product((0, 1), (0, 1))))
def test_invalid_common_history_preserves_the_admitted_legacy_requests(bank, taken):
    tx, memories = transaction(bank, valid=0, taken=taken), ScReference().memories
    assert history_requests(tx, memories) == sc_requests(tx, memories)
    with pytest.raises(ValueError, match='outside'):
        sc_requests(transaction(bank, valid=1, taken=taken), memories)


@pytest.mark.parametrize('field,value', (('valid', 2), ('ghr', -1), ('ghr', 1 << 16), ('bw', -1), ('bw', 1 << 8)))
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


@pytest.mark.parametrize('bit', range(16))
@pytest.mark.parametrize('bank', (0, 1))
def test_defaultconfig_long_global_history_single_bit_basis(bit, bank):
    tx = transaction(bank, ghr=1 << bit)
    indices = history_indices(tx['pc'], tx['resolve_meta']['commonHR'])
    assert indices['globalTable_0'] == (1 << (bit % 7) if bit < 8 else 0)
    assert indices['globalTable_1'] == 1 << (bit % 7)


@pytest.mark.parametrize('bw', range(256))
def test_defaultconfig_long_backward_history_all_encodings(bw):
    tx = transaction(bw=bw)
    indices = history_indices(tx['pc'], tx['resolve_meta']['commonHR'])
    assert indices['bwTable_0'] == bw & 15
    assert indices['bwTable_1'] == (bw & 127) ^ (bw >> 7)
