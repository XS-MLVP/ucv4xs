"""Actual eligible weight endpoints; not a repeated stable-output loop."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.sc.case.boundary import check_weight_boundary
from suites.frontend.bpu.sc.coverage.boundary import ScBoundaryCoverage


@pytest.mark.feature('BPU-SC-005')
@pytest.mark.parametrize('direction', (1, 0), ids=('upper-positive', 'lower-negative'))
async def test_distinct_delayed_sources_saturate_and_fresh_feedback_recovers(sc_agent, direction):
    coverage = ScBoundaryCoverage()
    try:
        await check_weight_boundary(sc_agent, coverage, direction=direction)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'sc'))
