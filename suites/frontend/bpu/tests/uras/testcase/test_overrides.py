"""MicroRAS S2/S3 override and priority paths."""

from __future__ import annotations

import pytest

from bpuverify.uras.transaction.types import UrasCycle
from bpuverify.uras.checker.assertions import pushed
from bpuverify.uras.case.definitions import CALL_A
from bpuverify.uras.case.definitions import CALL_B


@pytest.mark.feature("BPU-URAS-003")
async def test_s2_override_push_and_pop(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.cycle(
        UrasCycle(
            s2_valid=1,
            s2_start_pc=CALL_B.start_pc,
            s2_position=CALL_B.position,
            s2_action=2,
        )
    ) == pushed(CALL_B)
    assert (await uras_agent.cycle(UrasCycle(s2_valid=1, s2_action=1))).usable == 0


@pytest.mark.feature("BPU-URAS-004")
async def test_s3_override_push_and_pop(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.cycle(
        UrasCycle(
            s3_valid=1,
            s3_start_pc=CALL_A.start_pc,
            s3_position=CALL_A.position,
            s3_action=2,
        )
    ) == pushed(CALL_A)
    assert (await uras_agent.cycle(UrasCycle(s3_valid=1, s3_action=1))).usable == 0


@pytest.mark.feature("BPU-URAS-005")
async def test_s3_override_has_priority_over_s2_and_s1(uras_agent):
    await uras_agent.reset()
    actual = await uras_agent.cycle(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
            s2_valid=1,
            s2_start_pc=CALL_A.start_pc,
            s2_position=CALL_A.position,
            s2_action=2,
            s3_valid=1,
            s3_start_pc=CALL_B.start_pc,
            s3_position=CALL_B.position,
            s3_action=2,
        )
    )
    assert actual == pushed(CALL_B)
