"""MicroRAS redirect recovery bubble."""

from __future__ import annotations

import pytest

from bpuverify.uras.transaction.types import UrasCycle
from bpuverify.uras.transaction.types import UrasResult
from bpuverify.uras.case.definitions import MAIN_TOP


@pytest.mark.feature("BPU-URAS-006")
async def test_redirect_inserts_one_recovery_bubble(uras_agent):
    await uras_agent.reset()
    assert (await uras_agent.cycle(UrasCycle(has_redirect=1))).usable == 0
    assert (
        await uras_agent.cycle(UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP))
    ).usable == 0
    assert await uras_agent.cycle(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
    ) == UrasResult(1, MAIN_TOP)
