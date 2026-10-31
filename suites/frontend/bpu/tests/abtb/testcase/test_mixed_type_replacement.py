"""A conditional replacement must reset a former nonconditional way's counter."""

from __future__ import annotations

from dataclasses import replace

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_mixed_type_replacement_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_mixed_type_replacement_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import fill_taken_position_set
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import maybe_matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import interior_set_vectors
from suites.frontend.bpu.abtb.case.definitions import same_pc_position_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


BANK = 3
SET = 0


def assert_replacement_state(prediction, originals, original_ways, newcomer, victim, taken):
    assert (prediction.meta["setIdx"], prediction.meta["bankMask"]) == (SET, 1 << BANK)
    assert sum(entry.valid for entry in prediction.entries) == NUM_WAYS
    new_way, new_entry = matching_entry(
        prediction, newcomer.position, newcomer.branch_type
    )
    assert new_way == original_ways[victim.position]
    assert (new_entry.taken, new_entry.target) == (taken, newcomer.target)

    for original in originals:
        found = maybe_matching_entry(
            prediction, original.position, original.branch_type
        )
        if original == victim:
            assert found is None
            continue
        assert found is not None
        way, entry = found
        assert way == original_ways[original.position]
        assert (entry.taken, entry.target) == (
            int(original.branch_type != 1), original.target
        )


@pytest.mark.feature("BPU-ABTB-038")
async def test_replacing_mixed_type_way_resets_conditional_counter(abtb_agent):
    coverage = abtb_mixed_type_replacement_coverage_model()
    base = same_pc_position_vectors(BANK, SET)
    dummy = interior_set_vectors(BANK, SET)[1:]
    seen_ways = set()
    seen_types = set()

    for prefix in range(NUM_WAYS):
        await abtb_agent.reset()
        for vector in dummy[:prefix]:
            cold = await abtb_agent.predict(vector.pc, path_hash=BANK)
            assert_miss(cold)
            await train_taken(abtb_agent, vector, cold.meta)

        # Rotate branch types across replacement histories so the victim is
        # exercised both as a conditional and as a nonconditional resident.
        types = (1, 2, 1, 3)
        rotated = types[prefix:] + types[:prefix]
        originals = tuple(
            replace(vector, branch_type=branch_type)
            for vector, branch_type in zip(base[:NUM_WAYS], rotated, strict=True)
        )
        full, original_ways = await fill_taken_position_set(
            abtb_agent, originals, path_hash=BANK
        )
        assert (full.meta["setIdx"], full.meta["bankMask"]) == (SET, 1 << BANK)

        newcomer = base[NUM_WAYS]
        await train_taken(abtb_agent, newcomer, full.meta)
        replaced = await abtb_agent.predict(newcomer.pc, path_hash=BANK)
        evicted = tuple(
            vector for vector in originals
            if maybe_matching_entry(replaced, vector.position, vector.branch_type) is None
        )
        assert len(evicted) == 1, (prefix, replaced)
        victim = evicted[0]
        victim_way = original_ways[victim.position]
        assert_replacement_state(
            replaced, originals, original_ways, newcomer, victim, taken=1
        )
        coverage.sample({"scenario": "weak_positive"})

        await train_conditional_direction(
            abtb_agent, newcomer, replaced, taken=0
        )
        aged = await abtb_agent.predict(newcomer.pc, path_hash=BANK)
        assert_replacement_state(
            aged, originals, original_ways, newcomer, victim, taken=0
        )
        coverage.sample({"scenario": "not_taken"})

        await train_taken(abtb_agent, newcomer, aged.meta)
        recovered = await abtb_agent.predict(newcomer.pc, path_hash=BANK)
        assert_replacement_state(
            recovered, originals, original_ways, newcomer, victim, taken=1
        )
        coverage.sample({"scenario": "recovered"})
        coverage.sample({"scenario": f"way_{victim_way}"})
        victim_label = {1: "conditional", 2: "direct", 3: "indirect"}[victim.branch_type]
        coverage.sample({"scenario": f"victim_{victim_label}"})
        seen_ways.add(victim_way)
        seen_types.add(victim.branch_type)

    assert seen_ways == set(range(NUM_WAYS))
    assert seen_types == {1, 2, 3}
    coverage.assert_coverage(100.0)
    write_abtb_mixed_type_replacement_coverage(coverage, REPO_ROOT)
