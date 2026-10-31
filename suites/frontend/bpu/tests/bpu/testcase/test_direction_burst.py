"""Both ownership directions, no bank/set/depth Cartesian expansion."""
import pytest
from suites.frontend.bpu.bpu.case.direction_burst import check_direction_burst
from suites.frontend.bpu.bpu.coverage.direction_burst import DirectionBurstCoverage


@pytest.mark.feature('BPU-INT-090')
@pytest.mark.parametrize('original_way',(0,1),ids=('old-way0','old-way1'))
async def test_distinct_old_sources_overlap_and_saturate_the_current_retained_owner(bpu_agent,bpu_sc_output,original_way):
    coverage=DirectionBurstCoverage(original_way)
    try:await check_direction_burst(bpu_agent,coverage,original_way)
    finally:coverage.write(bpu_sc_output)
