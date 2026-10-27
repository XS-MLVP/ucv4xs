"""Same-bank adjacent sets retain independent four-way direction counters."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_adjacent_set_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_adjacent_set_direction_coverage
from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import interior_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


BANK = 1
NEIGHBOR_SET = 34
TARGET_SET = 35


@pytest.mark.feature("BPU-ABTB-024")
async def test_adjacent_interior_sets_keep_four_way_counters_isolated(abtb_agent):
    coverage = abtb_adjacent_set_direction_coverage_model()
    await abtb_agent.reset()

    residents = {}
    for set_index in (NEIGHBOR_SET, TARGET_SET):
        by_way = {}
        for vector in interior_set_vectors(BANK, set_index):
            cold = await abtb_agent.predict(vector.pc, path_hash=BANK)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                set_index, 1 << BANK
            )
            await train_taken(abtb_agent, vector, cold.meta)
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=1, path_hash=BANK
            )
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            assert way not in by_way
            by_way[way] = vector
        assert set(by_way) == set(range(NUM_WAYS))
        residents[set_index] = by_way

    # Keep all four neighboring counters at not-taken while exercising the
    # adjacent set. This catches both wrong-set updates and per-way leakage.
    for vector in residents[NEIGHBOR_SET].values():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=BANK
        )
        await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=BANK
        )

    expected_target = {way: 1 for way in range(NUM_WAYS)}

    async def assert_both_sets() -> None:
        for set_index, by_way in residents.items():
            for way, vector in by_way.items():
                expected = 0 if set_index == NEIGHBOR_SET else expected_target[way]
                observed = await assert_conditional_state(
                    abtb_agent, vector, taken=expected, path_hash=BANK
                )
                assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                    set_index, 1 << BANK
                )

    await assert_both_sets()
    for way, vector in residents[TARGET_SET].items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=BANK
        )
        current = await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=BANK
        )
        expected_target[way] = 0
        await assert_both_sets()
        coverage.sample({
            "set_35_transition": f"way_{way}_negative",
            "neighbor_state": "set_34_preserved",
        })

        for direction in (0, 1, 1, 1):
            await train_conditional_direction(
                abtb_agent, vector, current, taken=1
            )
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=BANK
            )
        expected_target[way] = 1
        await assert_both_sets()
        coverage.sample({
            "set_35_transition": f"way_{way}_positive",
            "neighbor_state": "set_34_preserved",
        })

    coverage.assert_coverage(100.0)
    write_abtb_adjacent_set_direction_coverage(coverage, REPO_ROOT)
