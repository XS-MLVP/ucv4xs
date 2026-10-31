"""MicroRAS address and position boundaries."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import BOUNDARIES


@pytest.mark.feature("BPU-URAS-007")
@pytest.mark.parametrize("vector", BOUNDARIES)
async def test_call_target_position_boundaries(uras_agent, vector):
    await uras_agent.reset()
    actual = await uras_agent.cycle(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=vector.start_pc,
            spec_position=vector.position,
            spec_action=2,
        )
    )
    assert actual == pushed(vector)


FULL_WIDTH = (1 << 50) - 2
# All address bits above the fetch-block offset, without wrapping when the
# largest legal position is added.
HIGH_PATTERN = ((1 << 50) - 1) & ~0xFF


@pytest.mark.feature("BPU-URAS-007")
async def test_full_width_address_bits_reach_the_public_target(uras_agent):
    """No address bit may be truncated between main top, corrections and output.

    Alternating a zero and an all-ones guarded address makes every public
    address bit take both values. The same pattern is exercised through the
    S1 call, S2 correction and S3 correction push paths.
    """
    from suites.frontend.bpu.uras.transaction.types import UrasResult
    from suites.frontend.bpu.uras.case.definitions import CallVector, MAIN_TOP

    await uras_agent.reset()
    for pattern in (0, FULL_WIDTH, 0):
        actual = await uras_agent.cycle(
            UrasCycle(s1_fire=1, full_ret_addr=pattern))
        assert actual == UrasResult(1, pattern), hex(pattern)

    for start in (0, 0x00F0, HIGH_PATTERN, 0x7FFF_FFFF, 0):
        for position in (0, 1, 2, 31):
            vector = CallVector(start, position)
            actual = await uras_agent.cycle(UrasCycle(
                s1_fire=1, spec_action=2,
                spec_start_pc=vector.start_pc,
                spec_position=vector.position,
                full_ret_addr=MAIN_TOP))
            assert actual == pushed(vector), ("s1", hex(start), position)

            actual = await uras_agent.cycle(UrasCycle(
                s1_fire=1, s2_valid=1, s2_action=2,
                s2_start_pc=vector.start_pc, s2_position=vector.position,
                full_ret_addr=MAIN_TOP))
            assert actual == pushed(vector), ("s2", hex(start), position)

            actual = await uras_agent.cycle(UrasCycle(
                s1_fire=1, s3_valid=1, s3_action=2,
                s3_start_pc=vector.start_pc, s3_position=vector.position,
                full_ret_addr=MAIN_TOP))
            assert actual == pushed(vector), ("s3", hex(start), position)

    # The S2 correction advances into the S3 return register only on s2_fire;
    # this is the storage path a later retiring correction reads.
    for start in (HIGH_PATTERN, 0x00F0, 0, 0x7FFF_FFFF, 0):
        for position in (0, 1, 15, 31):
            vector = CallVector(start, position)
            actual = await uras_agent.cycle(UrasCycle(
                s1_fire=1, s2_fire=1, s2_valid=1, s2_action=2,
                s2_start_pc=vector.start_pc, s2_position=vector.position,
                full_ret_addr=MAIN_TOP))
            assert actual == pushed(vector), ("s2-fire", hex(start), position)

    # Leave every full-width S2 storage bit cleared as well.
    await uras_agent.cycle(UrasCycle(
        s1_fire=1, spec_action=2, spec_start_pc=0, spec_position=0,
        full_ret_addr=MAIN_TOP))
