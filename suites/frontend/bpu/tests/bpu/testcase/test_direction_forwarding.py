"""Independent semantic state proves integrated adjacent dual-owner learning."""
import pytest

from bpuverify.bpu.case.direction_forwarding import check_direction_forwarding
from bpuverify.bpu.coverage.direction_forwarding import DirectionForwardingCoverage


@pytest.mark.feature('BPU-INT-085')
async def test_adjacent_old_read_feedback_forwards_opposite_owners_to_both_saturation_bounds(bpu_agent,bpu_sc_output):
    coverage=DirectionForwardingCoverage()
    try:await check_direction_forwarding(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
