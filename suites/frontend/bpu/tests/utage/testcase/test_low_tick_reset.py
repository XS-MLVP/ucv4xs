"""Sustained highest-table misses exercise low-table useful aging."""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.coverage.catalog import utage_low_tick_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_low_tick_coverage
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION
from bpuverify.common.env.paths import REPO_ROOT


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
