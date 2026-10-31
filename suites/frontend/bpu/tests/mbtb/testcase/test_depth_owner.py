"""Depth and logical owner with a real negative conditional neighbor."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.mbtb.case.depth_owner import check_depth_owner
from suites.frontend.bpu.mbtb.coverage.depth import DepthOwnerCoverage


@pytest.mark.feature('BPU-MBTB-025')
@pytest.mark.parametrize('stale', (False, True), ids=('fresh-source-control', 'real-old-cold-source'))
async def test_second_depth_rewrite_keeps_logical_owner_and_negative_peer(mbtb_agent, stale):
    coverage = DepthOwnerCoverage()
    try:
        await check_depth_owner(mbtb_agent, coverage, stale=stale)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))
