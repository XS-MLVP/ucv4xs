"""Autonomous service visibility, with SDK-confirmed SRAM write transfers."""
import pytest
from suites.frontend.bpu.bpu.case.direction_service import check_direction_service
from suites.frontend.bpu.bpu.coverage.direction_service import DirectionServiceCoverage


@pytest.mark.feature('BPU-INT-086')
async def test_nonreread_feedback_survives_continuous_same_bank_reads_until_actual_write_release(bpu_agent,bpu_sc_output):
    coverage=DirectionServiceCoverage()
    try:await check_direction_service(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
