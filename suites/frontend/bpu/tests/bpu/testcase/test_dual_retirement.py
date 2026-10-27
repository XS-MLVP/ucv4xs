"""Both migrated logical owners keep every concurrently retired successor."""
import pytest
from bpuverify.bpu.case.dual_retirement import check_dual_retirement
from bpuverify.bpu.coverage.dual_retirement import DualRetirementCoverage


@pytest.mark.feature('BPU-INT-090')
async def test_both_migrated_branch_successors_survive_simultaneous_previous_retirement_through_saturation_hold(bpu_agent, bpu_sc_output):
    coverage = DualRetirementCoverage()
    try:
        await check_dual_retirement(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
