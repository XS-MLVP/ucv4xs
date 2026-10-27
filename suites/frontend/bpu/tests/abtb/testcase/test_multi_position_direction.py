"""All-hit not-taken feedback and position-selective taken counter updates."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_multi_position_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_multi_position_direction_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_directions
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-036")
async def test_all_hit_not_taken_then_position_selective_taken(abtb_agent):
    coverage = abtb_multi_position_direction_coverage_model()
    await abtb_agent.reset()
    vectors = same_pc_position_vectors(0, 0)[:NUM_WAYS]
    cold = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_miss(cold)
    assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (0, 1)
    full, original_way = await fill_taken_position_set(
        abtb_agent, vectors, path_hash=0
    )

    await train_conditional_direction(
        abtb_agent, vectors[0], full, taken=0
    )
    all_negative = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        all_negative, vectors, original_way, (0, 0, 0, 0)
    )
    coverage.sample({"phase": "not_taken_decreases_all"})

    await train_taken(abtb_agent, vectors[2], all_negative.meta)
    middle_positive = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        middle_positive, vectors, original_way, (0, 0, 1, 0)
    )
    coverage.sample({"phase": "taken_restores_only_equal"})

    # Position 0 became strongly negative during the position-2 training.
    await train_taken(abtb_agent, vectors[0], middle_positive.meta)
    earlier_once = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        earlier_once, vectors, original_way, (0, 0, 1, 0)
    )
    coverage.sample({"phase": "earlier_decrease_proven"})

    await train_taken(abtb_agent, vectors[0], earlier_once.meta)
    earlier_twice = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        earlier_twice, vectors, original_way, (1, 0, 1, 0)
    )

    # Position 3 remained weakly negative; one taken update restores it.
    await train_taken(abtb_agent, vectors[3], earlier_twice.meta)
    last_positive = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        last_positive, vectors, original_way, (0, 0, 0, 1)
    )
    assert (last_positive.meta["setIdx"], last_positive.meta["bankMask"]) == (0, 1)
    coverage.sample({"phase": "later_unchanged_proven"})

    # The remaining interior position starts strongly negative; the two
    # accepted taken updates must restore that exact entry and no other one.
    await train_taken(abtb_agent, vectors[1], last_positive.meta)
    interior_once = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        interior_once, vectors, original_way, (0, 0, 0, 1)
    )
    await train_taken(abtb_agent, vectors[1], interior_once.meta)
    interior_twice = await abtb_agent.predict(vectors[0].pc, path_hash=0)
    assert_position_directions(
        interior_twice, vectors, original_way, (0, 1, 0, 1)
    )
    coverage.sample({"phase": "remaining_position_recovers"})

    coverage.assert_coverage(100.0)
    write_abtb_multi_position_direction_coverage(coverage, REPO_ROOT)
