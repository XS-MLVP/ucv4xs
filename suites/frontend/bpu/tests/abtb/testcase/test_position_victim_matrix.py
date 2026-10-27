"""Position-priority suppression holds for every replacement victim way."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_position_victim_matrix_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_position_victim_matrix_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import maybe_matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import interior_set_vectors
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


BANK = 1
SET = 36


@pytest.mark.feature("BPU-ABTB-035")
async def test_position_priority_survives_every_replacement_victim(abtb_agent):
    coverage = abtb_position_victim_matrix_coverage_model()
    vectors = same_pc_position_vectors(BANK, SET)
    dummy = interior_set_vectors(BANK, SET)[1:]
    victims = set()

    for prefix in range(NUM_WAYS):
        await abtb_agent.reset()
        for vector in dummy[:prefix]:
            cold = await abtb_agent.predict(vector.pc, path_hash=BANK)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                SET, 1 << BANK
            )
            await train_taken(abtb_agent, vector, cold.meta)

        full, original_way = await fill_taken_position_set(
            abtb_agent, vectors[:NUM_WAYS], path_hash=BANK
        )
        assert (full.meta["setIdx"], full.meta["bankMask"]) == (
            SET, 1 << BANK
        )
        late = vectors[NUM_WAYS]
        await train_taken(abtb_agent, late, full.meta)
        after = await abtb_agent.predict(late.pc, path_hash=BANK)
        assert (after.meta["setIdx"], after.meta["bankMask"]) == (
            SET, 1 << BANK
        )
        victim_way, new_entry = matching_entry(
            after, late.position, late.branch_type
        )
        assert (new_entry.taken, new_entry.target) == (1, late.target)

        evicted = []
        survivors = []
        for vector in vectors[:NUM_WAYS]:
            match = maybe_matching_entry(
                after, vector.position, vector.branch_type
            )
            if match is None:
                evicted.append(vector)
                continue
            way, entry = match
            assert way == original_way[vector.position]
            assert (entry.taken, entry.target) == (0, vector.target)
            survivors.append(vector)
        assert len(evicted) == 1
        assert len(survivors) == NUM_WAYS - 1
        assert original_way[evicted[0].position] == victim_way
        assert set(original_way.values()) == set(range(NUM_WAYS))
        for vector in dummy[:prefix]:
            assert_miss(await abtb_agent.predict(vector.pc, path_hash=BANK))

        victims.add(victim_way)
        coverage.sample({"victim_way": victim_way})

    assert victims == set(range(NUM_WAYS))
    coverage.assert_coverage(100.0)
    write_abtb_position_victim_matrix_coverage(coverage, REPO_ROOT)
