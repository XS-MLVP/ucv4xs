"""Conditional direction counter transitions and neighboring-set isolation."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL_NEIGHBOR
from suites.frontend.bpu.abtb.case.definitions import conditional_way_vectors


@pytest.mark.feature("BPU-ABTB-010")
async def test_conditional_counter_saturates_both_ways_without_touching_adjacent_set(abtb_agent):
    await abtb_agent.reset()
    first_cold = await abtb_agent.predict(CONDITIONAL.pc)
    neighbor_cold = await abtb_agent.predict(CONDITIONAL_NEIGHBOR.pc)
    assert first_cold.meta["setIdx"] != neighbor_cold.meta["setIdx"]
    await train_taken(abtb_agent, CONDITIONAL, first_cold.meta)
    await train_taken(abtb_agent, CONDITIONAL_NEIGHBOR, neighbor_cold.meta)

    current = await assert_conditional_state(abtb_agent, CONDITIONAL, taken=1)
    await assert_conditional_state(abtb_agent, CONDITIONAL_NEIGHBOR, taken=1)
    for _ in range(3):
        await train_conditional_direction(abtb_agent, CONDITIONAL, current, taken=0)
        current = await assert_conditional_state(abtb_agent, CONDITIONAL, taken=0)
        await assert_conditional_state(abtb_agent, CONDITIONAL_NEIGHBOR, taken=1)

    for expected in (0, 1, 1, 1):
        await train_conditional_direction(abtb_agent, CONDITIONAL, current, taken=1)
        current = await assert_conditional_state(abtb_agent, CONDITIONAL, taken=expected)
        await assert_conditional_state(abtb_agent, CONDITIONAL_NEIGHBOR, taken=1)


@pytest.mark.feature("BPU-ABTB-011")
async def test_conditional_counter_update_is_local_to_the_hit_way(abtb_agent):
    await abtb_agent.reset()
    vectors = conditional_way_vectors()
    path_hash = 0xB
    for vector in vectors:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert cold.meta["setIdx"] == 30
        assert cold.meta["bankMask"] == 8
        await train_taken(abtb_agent, vector, cold.meta)

    initial = [
        await assert_conditional_state(abtb_agent, vector, taken=1, path_hash=path_hash)
        for vector in vectors
    ]
    ways = [
        matching_entry(prediction, vector.position, vector.branch_type)[0]
        for vector, prediction in zip(vectors, initial, strict=True)
    ]
    assert sorted(ways) == list(range(len(vectors)))

    expected_taken = [1] * len(vectors)
    for index, vector in enumerate(vectors):
        observed = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=path_hash
        )
        await train_conditional_direction(abtb_agent, vector, observed, taken=0)
        expected_taken[index] = 0
        for other, expected in zip(vectors, expected_taken, strict=True):
            await assert_conditional_state(
                abtb_agent, other, taken=expected, path_hash=path_hash
            )
