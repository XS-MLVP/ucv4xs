"""Store-delay-only fixtures registered by the suite root conftest."""
from __future__ import annotations

import pytest

@pytest.fixture
def store_delay_factory(dut_factory):
    from suites.memblock.lsu.testbenches.store_delay.coverage import DelayPipelineCoverage
    from suites.memblock.lsu.testbenches.store_delay.env import StoreDelayEnv
    coverage = DelayPipelineCoverage()

    def create():
        return StoreDelayEnv(dut_factory('store_delay'), coverage)

    return create


@pytest.fixture
async def dly(store_delay_factory):
    env = store_delay_factory()
    async with env.running():
        await env.reset()
        yield env
