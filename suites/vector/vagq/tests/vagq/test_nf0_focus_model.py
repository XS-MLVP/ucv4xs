"""Pure qualification; no DUT or coverage credit."""
from collections import Counter
from copy import deepcopy

import pytest

from suites.vector.vagq.vagq.exhaustive import build_shape_sequence
from suites.vector.vagq.vagq.isa_reference import architectural_accesses
from suites.vector.vagq.vagq.nf0_focus import (
    PROFILES, assess_events, byte_mask_row, compatible_shapes, fired_response, make_variant, ready_values, shape_scope,
)
from suites.vector.vagq.vagq.scenario_matrix import legal_public_feature_cases
from suites.vector.vagq.vagq.types import Beat

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_scope_classifies_inventory_without_rewriting_or_removing_old_shapes():
    cases = tuple(legal_public_feature_cases())
    nf0 = [case for case in cases if case.nf == 0]
    assert len(cases) == 8352 and len(nf0) == 1450
    assert Counter(map(shape_scope, nf0)) == {
        'instruction_shape_compatible': 468,
        'vtype_unsupported': 126, 'indexed_data_eew_not_sew': 856,
    }
    assert Counter(case.operation for _, case in compatible_shapes()) == {op: 78 for op in (0, 1, 4, 5, 6, 7)}


def test_index_banks_share_the_right_data_mask_row_without_using_mop_declarations():
    # e8 data/e32 index: uops 0..3 consume the four index banks for data v8;
    # uops 4..7 consume those for v9. The rows MUST differ for sparse v0.
    mask = 0xA55A | (0x3CC3 << 16)
    assert [byte_mask_row(mask, data_eew=0, index_eew=2, uop_idx=i) for i in range(8)] == [0xA55A] * 4 + [0x3CC3] * 4
    # e32 data/e8 index: each uop owns a separate data register.
    assert [byte_mask_row(0b10100101, data_eew=2, index_eew=0, uop_idx=i) for i in range(2)] == [0x0F0F, 0xF0F0]


def test_every_selected_shape_has_real_full_uops_and_independent_variant_bytes():
    lengths = Counter()
    for ordinal, case in compatible_shapes():
        original = build_shape_sequence(case, ordinal)
        lengths[len(original.packets)] += 1
        for profile in PROFILES:
            variant = make_variant(case, ordinal, profile)
            first = variant.plan.packets[0][0]
            assert 0 <= first.vstart < first.vl <= case.vlmax
            assert len(variant.plan.packets) == len(original.packets)
            assert all(addr.nf == 0 and addr.uop_idx == i for i, (addr, _) in enumerate(variant.plan.packets))
            expected = Counter((access.element, access.address + byte)
                for access in architectural_accesses(kind='indexed' if case.indexed else 'strided',
                    base=original.base, vsew=case.vsew, vlmul=case.vlmul,
                    vl=first.vl, vstart=first.vstart, mask=variant.mask,
                    data_eew=case.data_eew, stride=original.stride,
                    index_values=original.index_values if case.indexed else None,
                    index_eew=case.index_eew)
                for byte in range(1 << case.data_eew))
            assert variant.plan.expected_bytes == expected
            if profile == 'zero_mask':
                assert not expected
    assert lengths == {1: 160, 2: 106, 4: 106, 8: 96}


def test_stalls_are_bounded_and_actually_exercise_each_lane():
    for group in range(3):
        history = [ready_values('stalled_sparse', cycle)[group] for cycle in range(40)]
        assert not any(any(values) for values in history[:12])
        for lane in range(len(history[0])):
            assert {values[lane] for values in history[12:]} == {True, False}


def test_response_never_acknowledges_valid_but_backpressured_requests():
    outputs = dict(io_lduReq_0_valid=1, io_lduReq_0_bits_meta_valid=1,
        io_lduReq_0_bits_meta_entryIdx=2, io_lduReq_0_bits_meta_byteOffset=4,
        io_lduReq_0_bits_meta_dataMask=0xF,
        io_lsqEmptyReq_0_valid=1, io_lsqEmptyReq_0_bits_entryIdx=3,
        io_lsqEmptyReq_0_bits_issueMask=0x100)
    stalled = fired_response(outputs, Beat(ldu_ready=(False, True, True), empty_ready=(False, True)))
    assert not any(value.valid for value in stalled.ldu_resp + stalled.empty_resp)
    accepted = fired_response(outputs, Beat())
    assert accepted.ldu_resp[0].issue_mask == 0xF0
    assert accepted.empty_resp[0].issue_mask == 0x100


def _migrated_request_example():
    ordinal, case = compatible_shapes()[0]
    variant = make_variant(case, ordinal, 'stalled_sparse')
    base = variant.plan.base
    requests = [dict(cycle=12 + element, kind='load', lane=0, entry=0,
        element=element, byte_offset=element, data_mask=1,
        address=base + 128 * element, rob=64, rob_flag=0) for element in range(2)]
    log = dict(admissions=[dict(entry=0)], data_admissions=[dict(entry=0)],
        writebacks=[dict(entry=0, rob=64, rob_flag=0, exception=0, uop_idx=0)],
        requests=requests, empty_requests=[], protocol_errors=[], timed_out=False,
        lane_reassignments=[dict(cycle=13, group='lduReq', lane=1)],
        responses=[dict(cycle=13 + element, kind='ldu', lane=0, entry=0, issue_mask=1 << element)
                   for element in range(2)])
    return variant, log


def test_decoupled_lane_reassignment_does_not_lose_or_duplicate_an_element():
    variant, log = _migrated_request_example()
    assessment, errors = assess_events(variant, log)
    assert not errors and assessment['request_boundary_status'] == 'PASS'
    assert assessment['overall_isa_acceptance'] == 'NOT_VERIFIED'


@pytest.mark.parametrize('mutation', ('lost', 'duplicate', 'wrong_address', 'wrong_element',
    'early_ack', 'ack_without_fire', 'missing_data_half', 'duplicate_writeback'))
def test_global_decoupled_checker_rejects_actual_corruption_despite_allowing_reassignment(mutation):
    variant, original = _migrated_request_example()
    log = deepcopy(original)
    if mutation == 'lost':
        log['requests'].pop()
    elif mutation == 'duplicate':
        log['requests'].append(deepcopy(log['requests'][0]))
    elif mutation == 'wrong_address':
        log['requests'][1]['address'] += 1
    elif mutation == 'wrong_element':
        log['requests'][1]['element'] = 2
    elif mutation == 'early_ack':
        log['responses'][1]['cycle'] -= 1
    elif mutation == 'ack_without_fire':
        log['responses'].append(dict(cycle=5, kind='ldu', lane=1, entry=0, issue_mask=2))
    elif mutation == 'missing_data_half':
        log['data_admissions'].clear()
    else:
        log['writebacks'].append(deepcopy(log['writebacks'][0]))
    assert assess_events(variant, log)[1]
