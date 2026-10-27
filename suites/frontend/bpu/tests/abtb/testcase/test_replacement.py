"""AheadBTB same-bank/set replacement isolation."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_boundary_replacement_coverage_model
from bpuverify.abtb.coverage.catalog import abtb_replacement_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_boundary_replacement_coverage
from bpuverify.abtb.coverage.catalog import write_abtb_replacement_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import SAME_SET_BANK_STRIDE
from bpuverify.abtb.case.definitions import conflict_vectors
from bpuverify.abtb.case.definitions import highest_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-005")
async def test_fifth_same_set_bank_entry_replaces_exactly_one_way(abtb_agent):
    await abtb_agent.reset()
    vectors = conflict_vectors()
    for vector in vectors:
        cold = await abtb_agent.predict(vector.pc)
        await train_taken(abtb_agent, vector, cold.meta)

    predictions = [await abtb_agent.predict(vector.pc) for vector in vectors]
    hits = [
        (vector, prediction)
        for vector, prediction in zip(vectors, predictions, strict=True)
        if any(entry.valid for entry in prediction.entries)
    ]

    assert len(hits) == NUM_WAYS
    assert any(entry.valid for entry in predictions[-1].entries)
    for vector, prediction in hits:
        assert_vector_hit(prediction, vector)


@pytest.mark.feature("BPU-ABTB-014")
async def test_replacement_resets_an_aged_conditional_counter(abtb_agent):
    await abtb_agent.reset()
    path_hash = 2  # bank 2, set 0 for this PC family
    base_pc = 0x4000_4800
    vectors = tuple(
        BranchVector(
            pc=base_pc + index * SAME_SET_BANK_STRIDE,
            target=0x4001_5000 + index * 0x20,
            position=1 + index * 2,
            branch_type=1,
        )
        for index in range(NUM_WAYS + 1)
    )

    for vector in vectors[:NUM_WAYS]:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (0, 4)
        await train_taken(abtb_agent, vector, cold.meta)

    original_ways = []
    for vector in vectors[:NUM_WAYS]:
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        way, entry = matching_entry(observed, vector.position, vector.branch_type)
        original_ways.append(way)
        assert (entry.taken, entry.target) == (1, vector.target)
        for _ in range(3):
            await train_conditional_direction(abtb_agent, vector, observed, taken=0)
            observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
            _, entry = matching_entry(observed, vector.position, vector.branch_type)
            assert (entry.taken, entry.target) == (0, vector.target)
    assert sorted(original_ways) == list(range(NUM_WAYS))

    newcomer = vectors[-1]
    cold = await abtb_agent.predict(newcomer.pc, path_hash=path_hash)
    assert_miss(cold)
    await train_taken(abtb_agent, newcomer, cold.meta)
    allocated = await abtb_agent.predict(newcomer.pc, path_hash=path_hash)
    replaced_way, entry = matching_entry(
        allocated, newcomer.position, newcomer.branch_type
    )
    assert replaced_way in original_ways
    assert (entry.taken, entry.target) == (1, newcomer.target)

    survivors = 0
    for vector, way in zip(vectors[:NUM_WAYS], original_ways, strict=True):
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        matches = [entry for entry in observed.entries if entry.valid]
        if way == replaced_way:
            assert not matches, (vector, observed)
        else:
            _, entry = matching_entry(observed, vector.position, vector.branch_type)
            assert (entry.taken, entry.target) == (0, vector.target)
            survivors += 1
    assert survivors == NUM_WAYS - 1


@pytest.mark.feature("BPU-ABTB-015")
async def test_sustained_same_set_replacement_reaches_every_way(abtb_agent):
    coverage = abtb_replacement_coverage_model()
    await abtb_agent.reset()
    path_hash = 2
    vectors = tuple(
        BranchVector(
            pc=0x4000_4800 + index * SAME_SET_BANK_STRIDE,
            target=0x4001_5000 + index * 0x20,
            position=index,
            branch_type=1,
        )
        for index in range(2 * NUM_WAYS)
    )
    residents: dict[int, BranchVector] = {}
    evicted: list[BranchVector] = []
    replacement_ways: set[int] = set()

    for index, vector in enumerate(vectors):
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (0, 4)
        await train_taken(abtb_agent, vector, cold.meta)
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        way, entry = matching_entry(observed, vector.position, vector.branch_type)
        assert (entry.taken, entry.target) == (1, vector.target)

        if index >= NUM_WAYS:
            assert way in residents
            replacement_ways.add(way)
            evicted.append(residents[way])
            coverage.sample({"victim_way": way})
        residents[way] = vector
        assert len(residents) == min(index + 1, NUM_WAYS)

    assert replacement_ways == set(range(NUM_WAYS))
    for vector in evicted:
        assert_miss(await abtb_agent.predict(vector.pc, path_hash=path_hash))
    for vector in residents.values():
        assert_vector_hit(
            await abtb_agent.predict(vector.pc, path_hash=path_hash), vector
        )
    coverage.assert_coverage(100.0)
    write_abtb_replacement_coverage(coverage, REPO_ROOT)


@pytest.mark.feature("BPU-ABTB-019")
async def test_highest_set_replacement_isolated_across_four_banks(abtb_agent):
    coverage = abtb_boundary_replacement_coverage_model()
    await abtb_agent.reset()
    survivors: list[tuple[int, BranchVector]] = []
    evicted: list[tuple[int, BranchVector]] = []

    for bank in range(4):
        vectors = highest_set_vectors(bank, 2 * NUM_WAYS)
        residents: dict[int, BranchVector] = {}
        for vector in vectors[:NUM_WAYS]:
            cold = await abtb_agent.predict(vector.pc, path_hash=bank)
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                63, 1 << bank
            )
            await train_taken(abtb_agent, vector, cold.meta)
            observed = await abtb_agent.predict(vector.pc, path_hash=bank)
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            residents[way] = vector
        assert set(residents) == set(range(NUM_WAYS))

        replacement_ways: set[int] = set()
        for newcomer in vectors[NUM_WAYS:]:
            cold = await abtb_agent.predict(newcomer.pc, path_hash=bank)
            assert_miss(cold)
            await train_taken(abtb_agent, newcomer, cold.meta)
            observed = await abtb_agent.predict(newcomer.pc, path_hash=bank)
            replaced_way, _ = matching_entry(
                observed, newcomer.position, newcomer.branch_type
            )
            assert_vector_hit(observed, newcomer)
            assert replaced_way in residents
            replacement_ways.add(replaced_way)
            prior = residents[replaced_way]
            assert_miss(await abtb_agent.predict(prior.pc, path_hash=bank))
            evicted.append((bank, prior))
            residents[replaced_way] = newcomer
            for vector in residents.values():
                assert_vector_hit(
                    await abtb_agent.predict(vector.pc, path_hash=bank), vector
                )
        assert replacement_ways == set(range(NUM_WAYS))
        survivors.extend((bank, vector) for vector in residents.values())
        coverage.sample({"bank_mask": observed.meta["bankMask"]})

    assert len(survivors) == 4 * NUM_WAYS
    assert len(evicted) == 4 * NUM_WAYS
    for bank, vector in survivors:
        assert_vector_hit(
            await abtb_agent.predict(vector.pc, path_hash=bank), vector
        )
    for bank, vector in evicted:
        assert_miss(await abtb_agent.predict(vector.pc, path_hash=bank))
    coverage.assert_coverage(100.0)
    write_abtb_boundary_replacement_coverage(coverage, REPO_ROOT)
