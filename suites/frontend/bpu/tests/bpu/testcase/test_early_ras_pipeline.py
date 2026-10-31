"""Three real calls overlap an adjacent or one-neutral-gap return."""
import pytest
from suites.frontend.bpu.bpu.case.ras.early import check_early_calls


@pytest.mark.feature('BPU-INT-068')
@pytest.mark.parametrize('gap', (0, 1))
async def test_early_ras_pipeline(bpu_agent, bpu_sc_output, gap):
    await check_early_calls(bpu_agent, bpu_sc_output, gap=gap)
