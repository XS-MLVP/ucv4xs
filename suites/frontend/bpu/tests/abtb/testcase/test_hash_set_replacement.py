"""Hash-selected interior-set replacement restores an aged counter."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_hash_replacement_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_hash_replacement_coverage
from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import hash_selected_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-026")
async def test_hash_selected_set_replacement_resets_each_aged_way(abtb_agent):
    path_hash = 7  # same bank as hash 3, but high hash bits select set 1
    vectors = hash_selected_set_vectors()
    coverage = abtb_hash_replacement_coverage_model()
    await abtb_agent.reset()

    residents = {}
    for vector in vectors[:NUM_WAYS]:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (1, 8)
        await train_taken(abtb_agent, vector, cold.meta)
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        way, _ = matching_entry(observed, vector.position, vector.branch_type)
        assert_vector_hit(observed, vector)
        residents[way] = vector
        await age_conditional_to_not_taken(
            abtb_agent, vector, observed, path_hash=path_hash
        )
    assert set(residents) == set(range(NUM_WAYS))

    replaced_ways = set()
    for newcomer in vectors[NUM_WAYS:]:
        cold = await abtb_agent.predict(newcomer.pc, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (1, 8)
        await train_taken(abtb_agent, newcomer, cold.meta)
        observed = await abtb_agent.predict(newcomer.pc, path_hash=path_hash)
        way, _ = matching_entry(observed, newcomer.position, newcomer.branch_type)
        assert way in residents
        assert_vector_hit(observed, newcomer)
        assert_miss(await abtb_agent.predict(residents[way].pc, path_hash=path_hash))
        for other_way, vector in residents.items():
            if other_way != way:
                await assert_conditional_state(
                    abtb_agent, vector, taken=0, path_hash=path_hash
                )
        replaced_ways.add(way)
        coverage.sample({"victim_way": way})
        residents[way] = newcomer
        await age_conditional_to_not_taken(
            abtb_agent, newcomer, observed, path_hash=path_hash
        )
    assert replaced_ways == set(range(NUM_WAYS))
    coverage.assert_coverage(100.0)
    write_abtb_hash_replacement_coverage(coverage, REPO_ROOT)
