"""Normal MicroRAS pipeline progression, distinct from overrides."""

from __future__ import annotations

import pytest

from bpuverify.uras.transaction.types import UrasCycle
from bpuverify.uras.transaction.types import UrasResult
from bpuverify.uras.checker.assertions import pushed
from bpuverify.uras.case.definitions import CALL_A
from bpuverify.uras.case.definitions import CALL_B
from bpuverify.uras.case.definitions import MAIN_TOP


@pytest.mark.feature("BPU-URAS-008")
async def test_s2_advance_and_s3_clear_release_speculative_push(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.pulse(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    ) == pushed(CALL_A)

    assert await uras_agent.pulse(UrasCycle(s2_fire=1)) == pushed(CALL_A)
    assert await uras_agent.pulse(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
    ) == pushed(CALL_A)
    assert await uras_agent.pulse(UrasCycle(s3_fire=1)) == pushed(CALL_A)
    assert await uras_agent.pulse(
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
    ) == UrasResult(1, MAIN_TOP)


@pytest.mark.feature("BPU-URAS-014")
async def test_s1_return_with_s2_call_and_older_s3_return_has_no_known_top(uras_agent):
    """A younger S2 call can pair with S1, but an older S3 return is unresolved.

    S1 accepts a return while a call is in S2 and an older return is in S3.
    The S2 call pairs with the S1 return, yet the earlier S3 return makes the
    resulting depth unpredictable, so the public result must be unusable and
    the target must not invent an address.
    """

    await uras_agent.reset()
    results = await uras_agent.stream(
        (
            UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
            UrasCycle(
                s1_fire=1,
                spec_start_pc=CALL_B.start_pc,
                spec_position=CALL_B.position,
                spec_action=2,
                s2_fire=1,
            ),
            UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
            UrasCycle(),
        )
    )
    assert results[1] == UrasResult(0, 0)
    assert results[2] == pushed(CALL_B)
    assert results[3] == UrasResult(0, 0)


@pytest.mark.feature("BPU-URAS-009")
async def test_neutral_s2_override_keeps_older_s3_push(uras_agent):
    await uras_agent.reset()
    assert await uras_agent.pulse(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    ) == pushed(CALL_A)
    assert await uras_agent.pulse(UrasCycle(s2_fire=1)) == pushed(CALL_A)

    # S2 changes to a no-op, but the older S3 CALL remains the effective top.
    assert await uras_agent.pulse(
        UrasCycle(s2_valid=1, s2_action=0, full_ret_addr=MAIN_TOP)
    ) == pushed(CALL_A)


@pytest.mark.feature("BPU-URAS-010")
async def test_s2_pop_override_pairs_with_older_s3_push(uras_agent):
    await uras_agent.reset()
    pop = UrasCycle(s2_valid=1, s2_action=1, full_ret_addr=MAIN_TOP)
    for _ in range(3):
        assert (await uras_agent.cycle(pop)).usable == 0

    await uras_agent.reset()
    assert await uras_agent.pulse(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    ) == pushed(CALL_A)
    assert await uras_agent.pulse(UrasCycle(s2_fire=1)) == pushed(CALL_A)

    # Hold the override long enough to verify the registered output, not a
    # stale result from the preceding S2 advance.
    for _ in range(3):
        assert await uras_agent.cycle(pop) == UrasResult(1, MAIN_TOP)


@pytest.mark.feature("BPU-URAS-011")
async def test_adjacent_s1_pop_then_neutral_pairs_with_older_s3_push(uras_agent):
    await uras_agent.reset()
    results = await uras_agent.stream(
        (
            UrasCycle(
                s1_fire=1,
                spec_start_pc=CALL_A.start_pc,
                spec_position=CALL_A.position,
                spec_action=2,
            ),
            UrasCycle(s2_fire=1),
            UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
            UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
            UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
            UrasCycle(),
        )
    )

    # The older S3 CALL alone would select its return address.  A pending S2
    # RETURN instead selects the main-RAS top for the adjacent neutral S1.
    assert results[1] == pushed(CALL_A)
    assert results[2] == pushed(CALL_A)
    assert results[3] == UrasResult(1, MAIN_TOP)
    assert results[4] == UrasResult(1, MAIN_TOP)
    assert results[5] == pushed(CALL_A)
