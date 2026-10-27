"""091: useful learning has its own deferred-service and consumer obligation."""
import pytest
from bpuverify.bpu.case.direction_useful import check_direction_useful
from bpuverify.bpu.coverage.direction_useful import DirectionUsefulCoverage


@pytest.mark.feature('BPU-INT-091')
async def test_original_disagreed_provider_useful_effects_survive_read_priority_until_committed_consumers(bpu_agent,bpu_sc_output):
    coverage=DirectionUsefulCoverage()
    try:await check_direction_useful(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
