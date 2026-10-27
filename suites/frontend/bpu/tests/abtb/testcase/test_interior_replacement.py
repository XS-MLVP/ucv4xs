"""Aged way replacement resets direction without disturbing a separate cell."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_interior_replacement_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_interior_replacement_coverage
from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import interior_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-030")
async def test_interior_bank_one_replacement_resets_aged_ways(abtb_agent):
    bank, set_index = 1, 34
    coverage = abtb_interior_replacement_coverage_model()
    await abtb_agent.reset()

    sentinel = interior_set_vectors(3, 16)[0]
    sentinel_cold = await abtb_agent.predict(sentinel.pc, path_hash=3)
    assert_miss(sentinel_cold)
    await train_taken(abtb_agent, sentinel, sentinel_cold.meta)
    assert_vector_hit(await abtb_agent.predict(sentinel.pc, path_hash=3), sentinel)

    vectors = interior_set_vectors(bank, set_index, 2 * NUM_WAYS)
    residents = {}
    for vector in vectors[:NUM_WAYS]:
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
        residents[way] = vector
        await age_conditional_to_not_taken(
            abtb_agent, vector, observed, path_hash=bank
        )
    assert set(residents) == set(range(NUM_WAYS))

    evicted = []
    replaced_ways = set()
    for newcomer in vectors[NUM_WAYS:]:
        cold = await abtb_agent.predict(newcomer.pc, path_hash=bank)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
            set_index, 1 << bank
        )
        await train_taken(abtb_agent, newcomer, cold.meta)
        observed = await assert_conditional_state(
            abtb_agent, newcomer, taken=1, path_hash=bank
        )
        way, _ = matching_entry(observed, newcomer.position, newcomer.branch_type)
        assert way in residents
        victim = residents[way]
        assert_miss(await abtb_agent.predict(victim.pc, path_hash=bank))
        for other_way, survivor in residents.items():
            if other_way != way:
                await assert_conditional_state(
                    abtb_agent, survivor, taken=0, path_hash=bank
                )
        assert_vector_hit(
            await abtb_agent.predict(sentinel.pc, path_hash=3), sentinel
        )
        coverage.sample({"victim_way": way, "sentinel": "preserved"})
        replaced_ways.add(way)
        evicted.append(victim)
        residents[way] = newcomer
        await age_conditional_to_not_taken(
            abtb_agent, newcomer, observed, path_hash=bank
        )

    assert len(evicted) == NUM_WAYS
    assert replaced_ways == set(range(NUM_WAYS))
    for vector in evicted:
        assert_miss(await abtb_agent.predict(vector.pc, path_hash=bank))
    for vector in residents.values():
        await assert_conditional_state(
            abtb_agent, vector, taken=0, path_hash=bank
        )
    assert_vector_hit(await abtb_agent.predict(sentinel.pc, path_hash=3), sentinel)
    coverage.assert_coverage(100.0)
    write_abtb_interior_replacement_coverage(coverage, REPO_ROOT)
