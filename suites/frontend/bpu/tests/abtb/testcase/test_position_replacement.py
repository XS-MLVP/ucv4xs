"""A later taken branch suppresses earlier conditions while replacing a way."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_position_replacement_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_position_replacement_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import fill_taken_position_set
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import maybe_matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import same_pc_position_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


BANK = 1
SET = 36


@pytest.mark.feature("BPU-ABTB-034")
async def test_later_taken_replacement_suppresses_all_surviving_earlier_branches(
    abtb_agent,
):
    coverage = abtb_position_replacement_coverage_model()
    await abtb_agent.reset()
    vectors = same_pc_position_vectors(BANK, SET)
    cold = await abtb_agent.predict(vectors[0].pc, path_hash=BANK)
    assert_miss(cold)
    assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (SET, 1 << BANK)

    full, original_way = await fill_taken_position_set(
        abtb_agent, vectors[:NUM_WAYS], path_hash=BANK
    )
    assert (full.meta["setIdx"], full.meta["bankMask"]) == (SET, 1 << BANK)
    coverage.sample({"phase": "full_set"})

    late = vectors[NUM_WAYS]
    await train_taken(abtb_agent, late, full.meta)
    after = await abtb_agent.predict(late.pc, path_hash=BANK)
    assert (after.meta["setIdx"], after.meta["bankMask"]) == (SET, 1 << BANK)
    new_way, new_entry = matching_entry(after, late.position, late.branch_type)
    assert (new_entry.taken, new_entry.target) == (1, late.target)
    surviving = []
    evicted = []
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
        surviving.append(vector)
    assert len(surviving) == NUM_WAYS - 1
    assert len(evicted) == 1
    assert original_way[evicted[0].position] == new_way
    coverage.sample({"phase": "later_taken_suppresses_survivors"})
    coverage.sample({"phase": "victim_replaced"})

    first = min(surviving, key=lambda vector: vector.position)
    await train_taken(abtb_agent, first, after.meta)
    recovered = await abtb_agent.predict(first.pc, path_hash=BANK)
    assert (recovered.meta["setIdx"], recovered.meta["bankMask"]) == (
        SET, 1 << BANK
    )
    _, restored = matching_entry(recovered, first.position, first.branch_type)
    assert (restored.taken, restored.target) == (1, first.target)
    for vector in surviving:
        if vector == first:
            continue
        _, held = matching_entry(recovered, vector.position, vector.branch_type)
        assert (held.taken, held.target) == (0, vector.target)
    _, late_held = matching_entry(recovered, late.position, late.branch_type)
    assert (late_held.taken, late_held.target) == (1, late.target)
    coverage.sample({"phase": "earlier_taken_restores_only_self"})

    coverage.assert_coverage(100.0)
    write_abtb_position_replacement_coverage(coverage, REPO_ROOT)
