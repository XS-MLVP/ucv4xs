"""Capacity+1 functional boundary, not a physical-coordinate sweep."""
import pytest
from suites.frontend.bpu.bpu.case.direction_replacement import check_direction_replacement
from suites.frontend.bpu.bpu.coverage.direction_replacement import DirectionReplacementCoverage


@pytest.mark.feature('BPU-INT-088')
async def test_full_retained_miss_preserves_new_seed_and_all_nonvictim_history_results(bpu_agent,bpu_sc_output):
    coverage=DirectionReplacementCoverage()
    try:await check_direction_replacement(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
