"""Distinct correct old directions oppose current confidence after migration."""
import pytest

from bpuverify.bpu.case.direction_turnaround import check_direction_turnaround
from bpuverify.bpu.coverage.direction_turnaround import DirectionTurnaroundCoverage
from bpuverify.bpu.model.tage.direction_turnaround import PROGRAMS


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_correct_opposed_source_learns_latest_retained_version(bpu_agent,bpu_sc_output,program):
    coverage=DirectionTurnaroundCoverage(program)
    try:await check_direction_turnaround(bpu_agent,program,coverage)
    finally:coverage.write(bpu_sc_output)
