"""Qualified tick/priority/clear/consumer lifecycle, no pin or cycle waits."""
import pytest
from suites.frontend.bpu.bpu.case.ittage_aging import check_aging


@pytest.mark.feature('BPU-INT-074')
async def test_ittage_qualified_tick_clear_and_retained_consumers(bpu_agent,bpu_sc_output):
    await check_aging(bpu_agent,bpu_sc_output)
