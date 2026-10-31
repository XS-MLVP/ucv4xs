"""Risk-directed counter transitions in representative interior bank/sets."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_interior_direction_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_interior_direction_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import interior_set_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-024")
async def test_interior_counters_recover_independently_per_bank_set_way(abtb_agent):
    coverage = abtb_interior_direction_coverage_model()
    await abtb_agent.reset()

    residents = {}
    for bank, set_index in ((3, 16), (1, 34)):
        by_way = {}
        for vector in interior_set_vectors(bank, set_index):
            cold = await abtb_agent.predict(vector.pc, path_hash=bank)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            await train_taken(abtb_agent, vector, cold.meta)
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=1, path_hash=bank
            )
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            by_way[way] = vector
        assert set(by_way) == set(range(NUM_WAYS))

        expected = {way: 1 for way in by_way}
        for way, vector in by_way.items():
            current = await assert_conditional_state(
                abtb_agent, vector, taken=1, path_hash=bank
            )
            for _ in range(3):
                await train_conditional_direction(abtb_agent, vector, current, taken=0)
                current = await assert_conditional_state(
                    abtb_agent, vector, taken=0, path_hash=bank
                )
            expected[way] = 0
            for other_way, other in by_way.items():
                await assert_conditional_state(
                    abtb_agent, other, taken=expected[other_way], path_hash=bank
                )
            coverage.sample({
                "cell_transition":
                f"bank_{bank}_set_{set_index}_way_{way}_negative_saturated"
            })

            for direction in (0, 1, 1, 1):
                await train_conditional_direction(abtb_agent, vector, current, taken=1)
                current = await assert_conditional_state(
                    abtb_agent, vector, taken=direction, path_hash=bank
                )
            expected[way] = 1
            for other_way, other in by_way.items():
                await assert_conditional_state(
                    abtb_agent, other, taken=expected[other_way], path_hash=bank
                )
            coverage.sample({
                "cell_transition":
                f"bank_{bank}_set_{set_index}_way_{way}_positive_saturated"
            })
        residents[bank, set_index] = by_way

    for (bank, set_index), by_way in residents.items():
        for vector in by_way.values():
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=1, path_hash=bank
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank
            )

    coverage.assert_coverage(100.0)
    write_abtb_interior_direction_coverage(coverage, REPO_ROOT)
