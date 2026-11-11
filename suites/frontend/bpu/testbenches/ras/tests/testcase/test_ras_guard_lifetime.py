"""The full restored address must survive a younger push/pop, not just one top read."""
import pytest
from suites.frontend.bpu.testbenches.ras.model.guarded_lifetime import CFI_BYTES
from suites.frontend.bpu.testbenches.ras.tests.scenarios.guarded_lifetime import check_guard_lifetime


@pytest.mark.feature('BPU-RAS-018')
@pytest.mark.parametrize('pc', CFI_BYTES)
async def test_guarded_restored_return_survives_younger_call_and_pop(ras_agent, pc):
    await check_guard_lifetime(ras_agent, pc)
