"""Depth-one retained ownership under same-bank pressure and opposite-bank flow."""
import itertools
import pytest
from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_depth_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_depth_coverage
from suites.frontend.bpu.mbtb.case import depth_scenario
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-MBTB-025')
async def test_depth_one_retains_record_owner_and_defined_neighbor_state(mbtb_agent):
    coverage = mbtb_depth_coverage_model()
    for align, bank, owner, phase, mode in itertools.product(
            range(2), range(2), range(2), ('clean_first', 'pending_second'), ('blocked', 'flow')):
        await depth_scenario.check_case(mbtb_agent, coverage, align, bank, owner, phase, mode)
    coverage.assert_coverage(100.0)
    write_mbtb_depth_coverage(coverage, REPO_ROOT)
