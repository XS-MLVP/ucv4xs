"""MicroRAS result monitor returns an immutable domain object."""

from __future__ import annotations

from bpuverify.uras.transaction.types import UrasCycle
from bpuverify.uras.transaction.types import UrasResult
from bpuverify.uras.case.definitions import MAIN_TOP


async def test_result_monitor_decodes_usable_and_target(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.cycle(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
    ) == UrasResult(1, MAIN_TOP)
