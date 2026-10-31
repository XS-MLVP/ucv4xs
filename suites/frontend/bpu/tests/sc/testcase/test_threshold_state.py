"""SC custom bounds, qualification and aggregate threshold state contracts."""
import pytest

from suites.frontend.bpu.sc.coverage.catalog import sc_threshold_bounds_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import sc_threshold_qualification_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import write_sc_threshold_bounds_coverage
from suites.frontend.bpu.sc.coverage.catalog import write_sc_threshold_qualification_coverage
from suites.frontend.bpu.sc.case.threshold_scenario import check_single_boundaries
from suites.frontend.bpu.sc.case.threshold_scenario import check_multi_boundaries
from suites.frontend.bpu.sc.case.threshold_scenario import check_qualification_and_aggregation
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-SC-021')
async def test_single_branch_threshold_reaches_rejects_and_leaves_both_bounds(sc_agent):
    coverage = sc_threshold_bounds_coverage_model('single')
    await check_single_boundaries(sc_agent, coverage)
    coverage.assert_coverage(100)
    write_sc_threshold_bounds_coverage(coverage, REPO_ROOT, 'single')


@pytest.mark.feature('BPU-SC-021')
async def test_four_same_way_branches_reject_whole_out_of_range_delta(sc_agent):
    coverage = sc_threshold_bounds_coverage_model('multi')
    await check_multi_boundaries(sc_agent, coverage)
    coverage.assert_coverage(100)
    write_sc_threshold_bounds_coverage(coverage, REPO_ROOT, 'multi')


@pytest.mark.feature('BPU-SC-022')
async def test_threshold_qualification_mixed_contributions_and_adjacent_feedback(sc_agent):
    coverage = sc_threshold_qualification_coverage_model()
    await check_qualification_and_aggregation(sc_agent, coverage)
    coverage.assert_coverage(100)
    write_sc_threshold_qualification_coverage(coverage, REPO_ROOT)
