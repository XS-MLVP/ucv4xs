"""A recovered direction change must return the non-priority shadow payload."""
import pytest

from bpuverify.bpu.case.abtb.recovery_cases import check_direction_recovery_case


@pytest.mark.feature('BPU-INT-057')
@pytest.mark.estimated_runtime(930)
async def test_direction_recovery_returns_upper_nonpriority_slot2_payload(bpu_agent, bpu_sc_output):
    await check_direction_recovery_case(bpu_agent, bpu_sc_output,
        bank=3, entry_set=63, table=1, slot=2)
