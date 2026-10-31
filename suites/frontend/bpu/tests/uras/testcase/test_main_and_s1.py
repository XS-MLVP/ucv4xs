"""MicroRAS main-RAS and S1 paths."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import CALL_A
from suites.frontend.bpu.uras.case.definitions import MAIN_TOP


@pytest.mark.feature("BPU-URAS-001")
async def test_main_ras_initializes_speculative_top(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.cycle(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
    ) == UrasResult(1, MAIN_TOP)


@pytest.mark.feature("BPU-URAS-002")
async def test_s1_push_and_following_pop_are_resolved(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.cycle(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    ) == pushed(CALL_A)
    assert await uras_agent.cycle(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP, spec_action=1)
    ) == UrasResult(1, MAIN_TOP)
