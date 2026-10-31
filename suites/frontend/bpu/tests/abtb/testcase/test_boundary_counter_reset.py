"""Replacement must reset a saturated counter at every highest-set way."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_boundary_counter_reset_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_boundary_counter_reset_coverage
from suites.frontend.bpu.abtb.checker.assertions import age_conditional_to_not_taken
from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import highest_set_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-021")
async def test_highest_set_replacement_resets_aged_counter_in_every_way(abtb_agent):
    coverage = abtb_boundary_counter_reset_coverage_model()
    await abtb_agent.reset()

    for bank in range(4):
        vectors = highest_set_vectors(bank, 2 * NUM_WAYS)
        residents = {}
        for vector in vectors[:NUM_WAYS]:
            cold = await abtb_agent.predict(vector.pc, path_hash=bank)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                63, 1 << bank
            )
            await train_taken(abtb_agent, vector, cold.meta)
            observed = await abtb_agent.predict(vector.pc, path_hash=bank)
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            assert_vector_hit(observed, vector)
            residents[way] = vector
            await age_conditional_to_not_taken(
                abtb_agent, vector, observed, path_hash=bank
            )
        assert set(residents) == set(range(NUM_WAYS))

        replaced_ways = set()
        for newcomer in vectors[NUM_WAYS:]:
            cold = await abtb_agent.predict(newcomer.pc, path_hash=bank)
            assert_miss(cold)
            await train_taken(abtb_agent, newcomer, cold.meta)
            observed = await abtb_agent.predict(newcomer.pc, path_hash=bank)
            way, _ = matching_entry(
                observed, newcomer.position, newcomer.branch_type
            )
            assert way in residents
            assert_vector_hit(observed, newcomer)
            assert_miss(await abtb_agent.predict(residents[way].pc, path_hash=bank))
            for other_way, vector in residents.items():
                if other_way != way:
                    await assert_conditional_state(
                        abtb_agent, vector, taken=0, path_hash=bank
                    )
            replaced_ways.add(way)
            coverage.sample({"bank_way_reset": f"bank_{bank}_way_{way}"})
            residents[way] = newcomer
            await age_conditional_to_not_taken(
                abtb_agent, newcomer, observed, path_hash=bank
            )
        assert replaced_ways == set(range(NUM_WAYS))

    coverage.assert_coverage(100.0)
    write_abtb_boundary_counter_reset_coverage(coverage, REPO_ROOT)
