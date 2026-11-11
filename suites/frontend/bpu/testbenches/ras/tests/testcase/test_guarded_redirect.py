"""The redirect producer supplies a real guard, not virtual sign extension."""
import pytest
from suites.frontend.bpu.testbenches.ras.tests.scenarios.guarded_redirect import check_guarded_call


@pytest.mark.feature('BPU-RAS-018')
@pytest.mark.parametrize('pc', (6, (1 << 49) + 6, (1 << 50) + 6,
                              (1 << 50) + (1 << 49) + 6, (1 << 51) - 2))
async def test_redirect_call_preserves_guard_even_when_different_from_virtual_sign(ras_agent, pc):
    await check_guarded_call(ras_agent, pc)
