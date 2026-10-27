"""Highest-set conditional counters remain local across banks and ways."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_boundary_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_boundary_direction_coverage
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import highest_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


async def _assert_matrix(agent, bank_ways, expected) -> None:
    for (bank, way), vector in bank_ways.items():
        observed = await assert_conditional_state(
            agent, vector, taken=expected[(bank, way)], path_hash=bank
        )
        assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
            63, 1 << bank
        )


@pytest.mark.feature("BPU-ABTB-020")
async def test_highest_set_counters_saturate_per_bank_and_way(abtb_agent):
    coverage = abtb_boundary_direction_coverage_model()
    await abtb_agent.reset()
    bank_ways = {}

    for bank in range(4):
        for vector in highest_set_vectors(bank):
            cold = await abtb_agent.predict(vector.pc, path_hash=bank)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                63, 1 << bank
            )
            await train_taken(abtb_agent, vector, cold.meta)
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=1, path_hash=bank
            )
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            bank_ways[(bank, way)] = vector

    assert set(bank_ways) == {
        (bank, way) for bank in range(4) for way in range(NUM_WAYS)
    }
    expected = {key: 1 for key in bank_ways}
    await _assert_matrix(abtb_agent, bank_ways, expected)

    for (bank, way), vector in bank_ways.items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=bank
        )
        for _ in range(3):
            await train_conditional_direction(abtb_agent, vector, current, taken=0)
            current = await assert_conditional_state(
                abtb_agent, vector, taken=0, path_hash=bank
            )
        expected[(bank, way)] = 0
        await _assert_matrix(abtb_agent, bank_ways, expected)
        coverage.sample({
            "bank_way_transition": f"bank_{bank}_way_{way}_negative_saturated"
        })

        for next_taken in (0, 1, 1, 1):
            await train_conditional_direction(abtb_agent, vector, current, taken=1)
            current = await assert_conditional_state(
                abtb_agent, vector, taken=next_taken, path_hash=bank
            )
        expected[(bank, way)] = 1
        await _assert_matrix(abtb_agent, bank_ways, expected)
        coverage.sample({
            "bank_way_transition": f"bank_{bank}_way_{way}_positive_saturated"
        })

    coverage.assert_coverage(100.0)
    write_abtb_boundary_direction_coverage(coverage, REPO_ROOT)
