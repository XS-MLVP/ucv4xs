"""Full-capacity retouch, not fifth-key overflow or bank/set enumeration."""
import pytest
from bpuverify.bpu.case.direction_capacity import check_direction_capacity
from bpuverify.bpu.coverage.direction_capacity import DirectionCapacityCoverage


@pytest.mark.feature('BPU-INT-087')
async def test_full_retained_capacity_retouch_preserves_every_owned_result_until_actual_sram_service(bpu_agent,bpu_sc_output):
    coverage=DirectionCapacityCoverage()
    try:await check_direction_capacity(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
