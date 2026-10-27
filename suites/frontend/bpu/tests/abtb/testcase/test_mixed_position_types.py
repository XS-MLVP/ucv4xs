"""Mixed same-PC branch types under shared direction and target feedback."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bpuverify.abtb.coverage.catalog import abtb_mixed_position_type_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_mixed_position_type_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_directions
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-037")
async def test_mixed_position_types_filter_direction_and_target_updates(abtb_agent):
    coverage = abtb_mixed_position_type_coverage_model()
    await abtb_agent.reset()
    base = same_pc_position_vectors(3, 0)[:NUM_WAYS]
    vectors = tuple(
        replace(vector, branch_type=branch_type)
        for vector, branch_type in zip(base, (1, 2, 1, 3), strict=True)
    )
    cold = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_miss(cold)
    assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (0, 8)
    full, original_way = await fill_taken_position_set(
        abtb_agent, vectors, path_hash=3
    )
    assert_position_directions(full, vectors, original_way, (1, 1, 1, 1))
    coverage.sample({"phase": "mixed_type_fill"})

    await train_conditional_direction(abtb_agent, vectors[0], full, taken=0)
    aged_once = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(aged_once, vectors, original_way, (0, 1, 0, 1))
    coverage.sample({"phase": "conditional_only_decrease"})

    await train_conditional_direction(
        abtb_agent, vectors[0], aged_once, taken=0
    )
    aged_twice = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(aged_twice, vectors, original_way, (0, 1, 0, 1))
    await train_taken(abtb_agent, vectors[2], aged_twice.meta)
    weak_negative = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(
        weak_negative, vectors, original_way, (0, 1, 0, 1)
    )
    coverage.sample({"phase": "negative_saturation_proven"})

    await train_taken(abtb_agent, vectors[2], weak_negative.meta)
    middle_restored = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(
        middle_restored, vectors, original_way, (0, 1, 1, 1)
    )
    await train_taken(abtb_agent, vectors[0], middle_restored.meta)
    early_once = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(early_once, vectors, original_way, (0, 1, 1, 1))
    await train_taken(abtb_agent, vectors[0], early_once.meta)
    recovered = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    assert_position_directions(recovered, vectors, original_way, (1, 1, 1, 1))
    coverage.sample({"phase": "conditional_recovery"})

    corrected_indirect = replace(vectors[3], target=vectors[3].target + 0x400)
    await train_taken(abtb_agent, corrected_indirect, recovered.meta)
    corrected = await abtb_agent.predict(vectors[0].pc, path_hash=3)
    expected_vectors = (*vectors[:3], corrected_indirect)
    assert_position_directions(
        corrected, expected_vectors, original_way, (0, 1, 0, 1)
    )
    assert (corrected.meta["setIdx"], corrected.meta["bankMask"]) == (0, 8)
    coverage.sample({"phase": "indirect_target_correction"})

    coverage.assert_coverage(100.0)
    write_abtb_mixed_position_type_coverage(coverage, REPO_ROOT)
