"""History-selected sets isolate same-PC multi-position direction training."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bpuverify.abtb.coverage.catalog import abtb_hash_position_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_hash_position_direction_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_directions
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-039")
async def test_hash_selected_set_keeps_four_position_directions_independent(abtb_agent):
    coverage = abtb_hash_position_direction_coverage_model()
    await abtb_agent.reset()

    # The low two history bits select bank 3; the next hash bits distinguish
    # physical set 0 (hash 3) from set 1 (hash 7) for this same fetch PC.
    base = same_pc_position_vectors(3, 0)[:NUM_WAYS]
    mixed = tuple(
        replace(vector, branch_type=kind, target=vector.target + 0x800)
        for vector, kind in zip(base, (1, 2, 1, 3), strict=True)
    )
    conditional = tuple(
        replace(vector, target=vector.target + 0x1000)
        for vector in base
    )
    assert all(vector.pc == base[0].pc for vector in (*mixed, *conditional))

    cold_zero = await abtb_agent.predict(base[0].pc, path_hash=3)
    cold_one = await abtb_agent.predict(base[0].pc, path_hash=7)
    assert_miss(cold_zero)
    assert_miss(cold_one)
    assert (cold_zero.meta["setIdx"], cold_zero.meta["bankMask"]) == (0, 8)
    assert (cold_one.meta["setIdx"], cold_one.meta["bankMask"]) == (1, 8)

    zero, zero_way = await fill_taken_position_set(
        abtb_agent, mixed, path_hash=3
    )
    one, one_way = await fill_taken_position_set(
        abtb_agent, conditional, path_hash=7
    )
    assert (zero.meta["setIdx"], zero.meta["bankMask"]) == (0, 8)
    assert (one.meta["setIdx"], one.meta["bankMask"]) == (1, 8)
    assert_position_directions(zero, mixed, zero_way, (1, 1, 1, 1))
    assert_position_directions(one, conditional, one_way, (1, 1, 1, 1))
    coverage.sample({"scenario": "two_distinct_profiles"})

    await train_conditional_direction(
        abtb_agent, conditional[0], one, taken=0
    )
    one = await abtb_agent.predict(base[0].pc, path_hash=7)
    zero = await abtb_agent.predict(base[0].pc, path_hash=3)
    assert_position_directions(one, conditional, one_way, (0, 0, 0, 0))
    assert_position_directions(zero, mixed, zero_way, (1, 1, 1, 1))
    coverage.sample({"scenario": "negative_set_isolated"})

    for selected, vector in enumerate(conditional):
        # Increasing the selected position also suppresses earlier positions.
        # Ascending order makes the new taken entry observable after each beat.
        await train_taken(abtb_agent, vector, one.meta)
        one = await abtb_agent.predict(base[0].pc, path_hash=7)
        zero = await abtb_agent.predict(base[0].pc, path_hash=3)
        expected = tuple(int(index == selected) for index in range(NUM_WAYS))
        assert_position_directions(one, conditional, one_way, expected)
        assert_position_directions(zero, mixed, zero_way, (1, 1, 1, 1))
        assert (one.meta["setIdx"], one.meta["bankMask"]) == (1, 8)
        assert (zero.meta["setIdx"], zero.meta["bankMask"]) == (0, 8)
        coverage.sample({"scenario": f"recovered_way_{one_way[vector.position]}"})

    assert set(one_way.values()) == set(range(NUM_WAYS))
    coverage.sample({"scenario": "mixed_set_preserved"})
    coverage.assert_coverage(100.0)
    write_abtb_hash_position_direction_coverage(coverage, REPO_ROOT)
