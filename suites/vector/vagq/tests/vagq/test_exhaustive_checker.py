"""Qualification of the exhaustive stimulus adapter/checker, never DUT credit."""
from collections import Counter
from copy import deepcopy

import pytest

from vagqverify.vagq.exhaustive import (
    assess_shape_boundaries, build_shape_sequence, compare_shape, index_value, observed_bytes,
)
from vagqverify.vagq.scenario_matrix import FeatureCase, legal_public_feature_cases


pytestmark = pytest.mark.toffee_functional_coverage(False)


def _simple():
    case = FeatureCase(0, 3, 0, 3, 0, 0, 2, 1)
    plan = build_shape_sequence(case, 0)
    requests = [dict(kind='load', entry=0, element=element, byte_offset=element * 8,
                     data_mask=0xFF, address=plan.base + element * plan.stride,
                     rob=64, rob_flag=0) for element in range(2)]
    log = dict(admissions=[dict(entry=0)],
        writebacks=[dict(entry=0, rob=64, rob_flag=0, exception=0, uop_idx=0)],
        requests=requests, timed_out=False)
    return plan, log


def test_checker_checks_all_bytes_and_rejects_duplicate_requests():
    plan, log = _simple()
    assert compare_shape(plan, log)['status'] == 'PASS'
    changed = deepcopy(log)
    changed['requests'][0]['data_mask'] = 1
    assert compare_shape(plan, changed)['missing_byte_occurrences'] == 7
    changed = deepcopy(log)
    changed['requests'].append(changed['requests'][0])
    verdict = compare_shape(plan, changed)
    assert verdict['status'] == 'FAIL'
    assert verdict['extra_byte_occurrences'] == 8
    assert len(verdict['duplicate_placements']) == 8


def test_checker_rejects_missing_uops_duplicate_writebacks_and_wrong_owner():
    plan, log = _simple()
    for mutate in (
        lambda x: x['admissions'].clear(),
        lambda x: x['writebacks'].append(x['writebacks'][0]),
        lambda x: x['requests'][0].update(rob=65),
        lambda x: x.update(timed_out=True),
    ):
        changed = deepcopy(log)
        mutate(changed)
        assert compare_shape(plan, changed)['status'] == 'FAIL'


def test_response_placement_retains_raw_spill_as_separate_diagnostic():
    req = dict(element=0, address=0x1000, data_mask=0xFFFF, byte_offset=12, entry=0)
    raw, placed, locations = observed_bytes([req])
    assert sum(raw.values()) == 16
    assert sum(placed.values()) == 4
    assert sum(locations.values()) == 4
    assert raw[(0, 0x100F)] == 1
    assert placed[(0, 0x100F)] == 0


def test_boundary_assessment_does_not_mislabel_spill_as_an_address_failure():
    case = FeatureCase(0, 0, 5, 1, 0, 4, 2, 2)
    plan = build_shape_sequence(case, 12)
    requests = [dict(kind='load', entry=0, element=i, byte_offset=i * 10,
                     data_mask=0x3FF, address=plan.base + i * plan.stride,
                     rob=64, rob_flag=0) for i in range(2)]
    log = dict(admissions=[dict(entry=i) for i in range(len(plan.packets))],
        writebacks=[dict(entry=i, rob=64, rob_flag=0, exception=0, uop_idx=i)
                    for i in range(len(plan.packets))], requests=requests, timed_out=False)
    result = assess_shape_boundaries(plan, log)
    assert result['architectural_requests']['status'] == 'PASS'
    assert result['public_lifecycle']['status'] == 'PASS'
    assert result['request_boundary_status'] == 'PASS'
    assert result['response_placement']['spilled_request_byte_occurrences'] == 4
    assert result['response_placement']['projection_matches_architecture'] is False
    assert result['legacy_v2']['status'] == 'FAIL'
    assert result['overall_isa_acceptance'] == 'NOT_VERIFIED'
    assert result['full_data_and_memory_effect']['status'] == 'NOT_VERIFIED'


@pytest.mark.parametrize('mutation', ('missing_byte', 'duplicate_request', 'wrong_address', 'wrong_element'))
def test_separate_request_checker_still_rejects_architectural_counterexamples(mutation):
    plan, log = _simple()
    if mutation == 'missing_byte':
        log['requests'][0]['data_mask'] ^= 0x80
    elif mutation == 'duplicate_request':
        log['requests'].append(deepcopy(log['requests'][0]))
    elif mutation == 'wrong_address':
        log['requests'][0]['address'] += 1
    else:
        log['requests'][0]['element'] = 1
    result = assess_shape_boundaries(plan, log)
    assert result['architectural_requests']['status'] == 'FAIL'
    assert result['request_boundary_status'] == 'FAIL'
    assert result['overall_isa_acceptance'] == 'NOT_VERIFIED'


@pytest.mark.parametrize('mutation', ('wrong_owner', 'duplicate_writeback', 'missing_admission', 'timeout'))
def test_matching_raw_bytes_cannot_hide_lifecycle_failures(mutation):
    plan, log = _simple()
    if mutation == 'wrong_owner':
        log['requests'][0]['rob'] = 65
    elif mutation == 'duplicate_writeback':
        log['writebacks'].append(deepcopy(log['writebacks'][0]))
    elif mutation == 'missing_admission':
        log['admissions'].clear()
    else:
        log['timed_out'] = True
    result = assess_shape_boundaries(plan, log)
    assert result['architectural_requests']['status'] == 'PASS'
    assert result['public_lifecycle']['status'] == 'FAIL'
    assert result['request_boundary_status'] == 'FAIL'


def test_even_a_fully_matching_projection_does_not_grant_isa_acceptance():
    plan, log = _simple()
    result = assess_shape_boundaries(plan, log)
    assert result['request_boundary_status'] == 'PASS'
    assert result['response_placement']['projection_matches_architecture'] is True
    assert result['overall_isa_acceptance'] == 'NOT_VERIFIED'


def test_all_inventory_cases_have_full_length_width_safe_producer_sequences():
    sequence_lengths = set()
    cases = tuple(legal_public_feature_cases())
    assert len(cases) == 8352
    for ordinal, case in enumerate(cases):
        plan = build_shape_sequence(case, ordinal)
        assert len(plan.packets) == len(plan.layout)
        sequence_lengths.add(len(plan.packets))
        assert sum(plan.expected_bytes.values()) == case.vlmax * (case.nf + 1) * (1 << case.data_eew)
        for i, (addr, data) in enumerate(plan.packets):
            assert addr.vl == case.vlmax
            assert addr.uop_idx == i
            assert addr.last_uop == (i == len(plan.packets) - 1)
            assert addr.rob_value == data.rob_value == 64
            assert 0 <= data.op2_data < (1 << 128)
            assert 0 <= addr.sq_value < 64 and 0 <= addr.lq_value < 128
            if not case.indexed:
                assert addr.ieew == case.data_eew
            else:
                slots = 16 >> case.index_eew
                bits = 8 << case.index_eew
                for mop in plan.layout[i]:
                    if mop.valid_bit:
                        actual = (data.op2_data >> ((mop.index % slots) * bits)) & ((1 << bits) - 1)
                        assert actual == index_value(mop.index, case.index_eew)
    assert sequence_lengths == set(range(1, 9))
