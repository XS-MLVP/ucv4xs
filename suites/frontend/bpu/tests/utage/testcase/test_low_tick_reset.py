"""Sustained highest-table misses exercise low-table useful aging."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.coverage.catalog import utage_low_tick_coverage_model
from suites.frontend.bpu.utage.coverage.catalog import write_utage_low_tick_coverage
from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.runtime.paths import REPO_ROOT


LOW_TICK_FAILURES = 130  # bit 7 is asserted after 128 failed allocations


@pytest.mark.feature("BPU-UTAGE-011")
async def test_low_table_tick_ages_useful_after_sustained_failed_allocations(utage_agent):
    await utage_agent.reset()
    coverage = utage_low_tick_coverage_model()
    cold = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert cold.hit == 0
    await utage_agent.train(UtageTraining(PASSING_PC, POSITION, 1, cold.meta))
    first = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (first.hit, first.taken, first.meta["abtbResult"][0]["tableId"]) == (1, 1, 0)

    # Preserve a useful lower-table resident while escalating to the highest
    # table. Correct provider training raises its useful count before the
    # opposite outcome allocates the higher provider.
    await utage_agent.train(
        UtageTraining(PASSING_PC, POSITION, 1, first.meta, mispredict=0)
    )
    first = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (first.hit, first.taken) == (1, 1)
    await utage_agent.train(UtageTraining(PASSING_PC, POSITION, 0, first.meta))
    highest = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert highest.hit == 1
    assert highest.meta["abtbResult"][0]["tableId"] == 1

    read_index = highest.meta["readIndex"]
    alias_position = POSITION + 1
    alias_cold = await utage_agent.predict(PASSING_PC, alias_position, 0)
    assert alias_cold.hit == 0
    assert alias_cold.meta["readIndex"] == read_index
    await utage_agent.train(
        UtageTraining(PASSING_PC, alias_position, 1, alias_cold.meta)
    )
    blocked = await utage_agent.predict(PASSING_PC, alias_position, 0)
    assert blocked.hit == 0  # Both useful entries still block allocation.
    coverage.sample({"outcome": "blocked", "provider": "none"})

    for attempt in range(LOW_TICK_FAILURES):
        actual = 1 - highest.taken
        await utage_agent.train(
            UtageTraining(PASSING_PC, POSITION, actual, highest.meta)
        )
        highest = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert highest.hit == 1, attempt
        assert highest.meta["abtbResult"][0]["tableId"] == 1, attempt
        assert highest.meta["readIndex"] == read_index, attempt

    alias_cold = await utage_agent.predict(PASSING_PC, alias_position, 0)
    assert alias_cold.hit == 0
    await utage_agent.train(
        UtageTraining(PASSING_PC, alias_position, 1, alias_cold.meta)
    )
    reopened = await utage_agent.predict(PASSING_PC, alias_position, 0)
    assert reopened.hit == 1
    assert reopened.meta["abtbResult"][0]["tableId"] == 0
    coverage.sample({"outcome": "reopened", "provider": "lower"})
    original = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert original.hit == 1
    assert original.meta["abtbResult"][0]["tableId"] == 1
    coverage.sample({"outcome": "preserved", "provider": "higher"})
    coverage.assert_coverage(100.0)
    write_utage_low_tick_coverage(coverage, REPO_ROOT)


# The shadow buffer owns the full 4-bank x 128-set useful array, so one aging
# sweep is a whole-array operation. Populate every table-0 cell with useful=1
# through genuine allocations, then let a highest-table miss stream reach the
# 128-failure aging tick. This is the complete semantic case for
# "aging decrements every nonzero useful counter", not an enumeration of one
# physical register.
ALL_USEFUL_PCS = 0x4000_0000


@pytest.mark.feature("BPU-UTAGE-028")
@pytest.mark.estimated_runtime(300)
async def test_every_useful_cell_is_aged_by_one_global_sweep(utage_agent):
    await utage_agent.reset()
    base = ALL_USEFUL_PCS
    # index0 = (pc[8:5] << 5) | (pc[4:0] ^ fold(history,5,5)); with a zero
    # low-five-bit PC and history = index & 31 this covers all 512 indices.
    for index in range(512):
        pc = base + (index & 0x1E0)
        history = index & 0x1F
        cold = await utage_agent.predict(pc, POSITION, 0, folded_history=history)
        assert cold.hit == 0, (index, cold)
        assert cold.meta["readIndex"][0] == index, (index, cold.meta["readIndex"])
        await utage_agent.train(UtageTraining(pc, POSITION, 1, cold.meta))

    # Same table-0 index, different tag: the lower table already has useful
    # set, so this miss allocates the upper table instead.
    trigger_pc = base + 0x400 + 0x1E0
    trigger_history = 31
    cold = await utage_agent.predict(trigger_pc, POSITION, 0, folded_history=trigger_history)
    assert cold.hit == 0
    await utage_agent.train(UtageTraining(trigger_pc, POSITION, 1, cold.meta))
    highest = await utage_agent.predict(trigger_pc, POSITION, 0, folded_history=trigger_history)
    assert (highest.hit, highest.meta["abtbResult"][0]["tableId"]) == (1, 1)

    # Each fresh opposite outcome is a failed allocation; the 128th failure
    # crosses bit 7 and runs exactly one useful-array aging sweep.
    for attempt in range(LOW_TICK_FAILURES - 2):
        await utage_agent.train(UtageTraining(trigger_pc, POSITION, 0, highest.meta))
    observed = await utage_agent.predict(trigger_pc, POSITION, 0, folded_history=trigger_history)
    assert observed.hit == 1
