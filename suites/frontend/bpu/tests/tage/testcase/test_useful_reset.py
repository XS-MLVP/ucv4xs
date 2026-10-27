"""TAGE full-useful-set allocation pressure and counter-driven recovery."""

from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.catalog import tage_useful_reset_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_useful_reset_coverage
from bpuverify.tage.checker.assertions import fill_useful_set
from bpuverify.tage.checker.assertions import require_miss
from bpuverify.tage.checker.assertions import require_provider
from bpuverify.tage.checker.assertions import train_until_useful_reset_reopens_set
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import PRESSURE_POSITION
from bpuverify.tage.case.definitions import USEFUL_RESET_COUNTER_MAX
from bpuverify.tage.case.definitions import USEFUL_SET_POSITIONS
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-TAGE-009")
async def test_full_useful_set_blocks_new_allocation_without_evicting_entries(tage_agent):
    await tage_agent.reset()
    residents = await fill_useful_set(tage_agent)
    cold = await tage_agent.predict(PC, PRESSURE_POSITION, 0)
    require_miss(cold)

    await tage_agent.train(
        TageTraining(PC, PRESSURE_POSITION, 1, 0, cold.meta, 1)
    )
    require_miss(await tage_agent.predict(PC, PRESSURE_POSITION, 0))
    for position, before in residents.items():
        after = await tage_agent.predict(PC, position, 0)
        require_provider(after)
        assert after.meta["providerTableIdx"] == before.meta["providerTableIdx"]
        assert after.meta["providerUsefulCtr_value"] > 0


@pytest.mark.feature("BPU-TAGE-010")
async def test_useful_reset_reopens_full_set_and_preserves_other_tags(tage_agent):
    await tage_agent.reset()
    coverage = tage_useful_reset_coverage_model()
    residents = await fill_useful_set(tage_agent)
    cold = await tage_agent.predict(PC, PRESSURE_POSITION, 0)
    require_miss(cold)
    await tage_agent.train(
        TageTraining(PC, PRESSURE_POSITION, 1, 0, cold.meta, 1)
    )
    blocked = await tage_agent.predict(PC, PRESSURE_POSITION, 0)
    require_miss(blocked)
    before = [
        await tage_agent.predict(PC, position, 0)
        for position in USEFUL_SET_POSITIONS
    ]
    assert all(
        entry.meta["hasProvider"] and entry.meta["providerUsefulCtr_value"] > 0
        for entry in before
    )
    coverage.sample({
        "allocation": "blocked",
        "resident_useful": "positive",
        "occupancy": len(before),
    })

    attempts, newcomer = await train_until_useful_reset_reopens_set(
        tage_agent, blocked, already_failed=1
    )
    assert USEFUL_RESET_COUNTER_MAX < attempts <= USEFUL_RESET_COUNTER_MAX + 5
    require_provider(newcomer)

    survivors = 0
    for position in USEFUL_SET_POSITIONS:
        after = await tage_agent.predict(PC, position, 0)
        if not after.meta["hasProvider"]:
            continue
        survivors += 1
        assert after.meta["providerTableIdx"] == residents[position].meta["providerTableIdx"]
        assert after.meta["providerUsefulCtr_value"] == 0
        assert after.meta["providerTakenCtr_value"] >= 5
    assert survivors == len(USEFUL_SET_POSITIONS) - 1
    coverage.sample({
        "allocation": "reopened",
        "resident_useful": "cleared",
        "occupancy": survivors,
    })
    coverage.assert_coverage(100.0)
    write_tage_useful_reset_coverage(coverage, REPO_ROOT)
