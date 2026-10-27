"""A bias row contains all selectors, not just one per base branch way."""

import pytest

from bpuverify.sc.coverage.catalog import sc_bias_selector_merge_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_bias_selector_merge_coverage
from bpuverify.sc.case.bias_selector_scenario import check_bias_selector_merge
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-019")
async def test_bias_selector_masks_merge_within_each_pending_row(sc_agent):
    coverage = sc_bias_selector_merge_coverage_model()
    await check_bias_selector_merge(sc_agent, coverage)
    coverage.assert_coverage(100)
    write_sc_bias_selector_merge_coverage(coverage, REPO_ROOT)
