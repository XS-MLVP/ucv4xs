"""Pure audit of the complete independent public feature-space generator."""
import pytest

from suites.vector.vagq.vagq.scenario_matrix import (
    PUBLIC_OPERATIONS,
    fault_positions,
    pairwise_tokens,
    legal_public_feature_cases,
    public_space_metadata,
    representative_public_feature_cases,
)


pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_public_feature_generator_is_unique_and_covers_all_operation_classes():
    cases = tuple(legal_public_feature_cases())
    keys = {
        (
            case.operation, case.vsew, case.vlmul, case.data_eew,
            case.index_eew, case.nf, case.uop_count,
        )
        for case in cases
    }
    assert len(keys) == len(cases)
    assert {case.operation for case in cases} == set(PUBLIC_OPERATIONS)
    assert {case.nf for case in cases} == set(range(8))
    assert {case.data_eew for case in cases} == set(range(4))
    assert {case.vlmul for case in cases} == set((5, 6, 7, 0, 1, 2, 3))
    assert len(cases) == 8352


def test_fault_generator_covers_every_architectural_element_in_each_shape():
    for case in legal_public_feature_cases():
        assert fault_positions(case) == tuple(range(case.vlmax))
        assert 1 <= case.uop_count <= 8


def test_real_dut_covering_set_covers_every_public_parameter_bin_and_pair():
    cases = representative_public_feature_cases()
    assert len(cases) == 80
    assert {case.operation for case in cases} == set(PUBLIC_OPERATIONS)
    assert {case.vsew for case in cases} == set(range(4))
    assert {case.vlmul for case in cases} == set((5, 6, 7, 0, 1, 2, 3))
    assert {case.data_eew for case in cases} == set(range(4))
    assert {case.index_eew for case in cases if case.indexed} == set(range(4))
    assert {case.nf for case in cases} == set(range(8))
    assert {case.uop_count for case in cases} == set(range(1, 9))


def test_pairwise_covering_set_and_space_accounting_are_explicit():
    legal = tuple(legal_public_feature_cases())
    representative = tuple(representative_public_feature_cases())
    legal_tokens = set().union(*(pairwise_tokens(case) for case in legal))
    selected_tokens = set().union(*(pairwise_tokens(case) for case in representative))
    assert len(legal_tokens) == 742
    assert selected_tokens == legal_tokens

    metadata = public_space_metadata()
    assert metadata['legal_case_count'] == 8352
    assert metadata['representative_case_count'] == 80
    assert metadata['representative_unique_case_count'] == 80
    assert metadata['pairwise_token_count'] == 742
    assert metadata['pairwise_covered_by_representative'] == 742
    assert metadata['pairwise_cross_count'] == 700
    assert metadata['pairwise_cross_covered_by_representative'] == 700
