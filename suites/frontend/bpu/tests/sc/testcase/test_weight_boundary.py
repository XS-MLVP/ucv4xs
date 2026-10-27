"""Actual eligible weight endpoints; not a repeated stable-output loop."""
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.sc.case.boundary import check_weight_boundary
from bpuverify.sc.coverage.boundary import ScBoundaryCoverage


@pytest.mark.feature('BPU-SC-005')
@pytest.mark.parametrize('direction', (1, 0), ids=('upper-positive', 'lower-negative'))
async def test_distinct_delayed_sources_saturate_and_fresh_feedback_recovers(sc_agent, direction):
    coverage = ScBoundaryCoverage()
    try:
        await check_weight_boundary(sc_agent, coverage, direction=direction)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'sc'))
