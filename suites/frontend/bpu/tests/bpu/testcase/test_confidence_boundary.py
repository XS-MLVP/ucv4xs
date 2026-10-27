"""Delayed correct learning crosses, holds and leaves confidence boundaries."""
import pytest
from bpuverify.bpu.case.confidence_boundary import check_confidence_boundary
from bpuverify.bpu.coverage.confidence_boundary import ConfidenceBoundaryCoverage
from bpuverify.bpu.model.tage.confidence_boundary import PROGRAMS


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_distinct_old_outcomes_cross_and_leave_current_confidence_bounds(bpu_agent,bpu_sc_output,program):
    coverage=ConfidenceBoundaryCoverage(program)
    try:await check_confidence_boundary(bpu_agent,program,coverage)
    finally:coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program',PROGRAMS[2:],ids=lambda p:p.name)
async def test_stable_history_preserves_complete_confidence_roundtrip(bpu_agent,bpu_sc_output,program):
    coverage=ConfidenceBoundaryCoverage(program,traffic='fallthrough')
    try:await check_confidence_boundary(bpu_agent,program,coverage,traffic='fallthrough')
    finally:coverage.write(bpu_sc_output)
