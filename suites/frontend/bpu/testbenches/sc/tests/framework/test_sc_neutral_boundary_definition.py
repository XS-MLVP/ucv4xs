"""A combined boundary obligation cannot borrow an old cold-state PASS."""
from suites.frontend.bpu.testbenches.bpu.tests.framework.test_parallel_matrices import EXTRA_MATRICES


def test_old_cold_cancellation_keeps_its_own_four_bins_without_fabricated_reached():
    factory, axes, cross, denominator = EXTRA_MATRICES['sc_legacy_same_way']
    assert denominator == len(axes['phase']) == 4 and cross is None
