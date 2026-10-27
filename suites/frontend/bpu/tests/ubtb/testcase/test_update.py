"""MicroBTB useful-counter mediated update behavior."""

from __future__ import annotations

import pytest

from bpuverify.ubtb.transaction.types import BranchTraining
from bpuverify.ubtb.checker.assertions import assert_miss
from bpuverify.ubtb.checker.assertions import expected_prediction
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import BranchVector
from bpuverify.ubtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-UBTB-005")
async def test_existing_entry_converges_to_changed_payload(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)
    changed = BranchVector(
        DIRECT.pc,
        DIRECT.target + 0x100,
        7,
        3,
    )

    observations = []
    for _ in range(4):
        await train_taken(ubtb_agent, changed)
        observations.append(await ubtb_agent.predict(DIRECT.pc))
        if observations[-1] == expected_prediction(changed):
            break

    assert observations[0] == expected_prediction(DIRECT)
    assert observations[-1] == expected_prediction(changed)


@pytest.mark.feature("BPU-UBTB-009")
async def test_not_taken_aging_reinitializes_a_useful_entry(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)
    assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(DIRECT)

    # The 2-bit useful counter starts at 3. Two decrements keep the old
    # prediction; the third reaches zero and invalidates the entry. Another
    # not-taken train must not allocate it again.
    for step in range(1, 5):
        await ubtb_agent.train(
            BranchTraining(
                pc=DIRECT.pc,
                target=DIRECT.target,
                taken=0,
                position=DIRECT.position,
                branch_type=DIRECT.branch_type,
            )
        )
        if step < 3:
            actual = await ubtb_agent.predict(DIRECT.pc)
            assert actual == expected_prediction(DIRECT), f"aging step {step}: {actual!r}"
        else:
            await assert_miss(ubtb_agent, DIRECT.pc)

    replacement = BranchVector(
        DIRECT.pc, DIRECT.target + 0x100, DIRECT.position, DIRECT.branch_type
    )
    await train_taken(ubtb_agent, replacement)
    assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(replacement)


@pytest.mark.feature("BPU-UBTB-010")
async def test_useful_counter_recovers_then_saturates_positive(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)

    await ubtb_agent.train(
        BranchTraining(
            pc=DIRECT.pc,
            target=DIRECT.target,
            taken=0,
            position=DIRECT.position,
            branch_type=DIRECT.branch_type,
        )
    )
    assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(DIRECT)

    # An exact taken hit recovers 2 -> 3. A further exact hit must hold at
    # positive saturation rather than wrapping the useful counter to zero.
    await train_taken(ubtb_agent, DIRECT)
    assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(DIRECT)
    for _ in range(2):
        await train_taken(ubtb_agent, DIRECT)
        assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(DIRECT)
