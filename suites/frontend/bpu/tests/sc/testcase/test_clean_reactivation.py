"""Existing drained rows must accept new masks without harming neighbors."""

import pytest

from suites.frontend.bpu.sc.coverage.catalog import sc_clean_reactivation_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import write_sc_clean_reactivation_coverage
from suites.frontend.bpu.sc.case.clean_reactivation_scenario import check_clean_reactivation
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-020")
async def test_drained_bias_rows_reactivate_selected_ways_and_preserve_neighbors(sc_agent):
    coverage = sc_clean_reactivation_coverage_model()
    await check_clean_reactivation(sc_agent, coverage)
    coverage.assert_coverage(100)
    write_sc_clean_reactivation_coverage(coverage, REPO_ROOT)
