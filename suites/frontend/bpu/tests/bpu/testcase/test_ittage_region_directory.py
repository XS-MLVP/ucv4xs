"""Capacity-driven region lifecycle, not a physical bank/set sweep."""
import pytest
from suites.frontend.bpu.bpu.case.ittage_capacity import check_directory


@pytest.mark.feature('BPU-INT-067')
async def test_region_capacity_reuse_and_replacement(bpu_agent, bpu_sc_output):
    await check_directory(bpu_agent, bpu_sc_output)
