"""Real high-index provider learning through distinct pipeline ancestors."""
import pytest

from suites.frontend.bpu.bpu.case.bypass.high_index import check_high_index


@pytest.mark.feature('BPU-INT-066')
async def test_high_index_lower_provider_useful_roles(bpu_agent, bpu_sc_output):
    await check_high_index(bpu_agent, bpu_sc_output)
