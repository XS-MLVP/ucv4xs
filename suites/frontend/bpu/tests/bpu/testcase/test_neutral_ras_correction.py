"""Natural neutral correction preserves an older call and flushes a younger call."""
import pytest
from bpuverify.bpu.case.ras.correction import check_neutral_correction


@pytest.mark.feature('BPU-INT-069')
async def test_neutral_correction_keeps_older_call_and_flushes_younger_call(bpu_agent, bpu_sc_output):
    await check_neutral_correction(bpu_agent, bpu_sc_output)


@pytest.mark.feature('BPU-INT-069')
async def test_neutral_correction_keeps_older_call_and_flushes_younger_return(bpu_agent,bpu_sc_output):
    await check_neutral_correction(bpu_agent,bpu_sc_output,younger_action=1)
