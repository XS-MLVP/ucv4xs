"""Four-way AheadBTB S2 sideband remains associated under history interleaving."""

from __future__ import annotations

from dataclasses import replace

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_microtage_vector_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_microtage_vector_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_position_directions
from suites.frontend.bpu.abtb.checker.assertions import fill_taken_position_set
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import same_pc_position_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


def assert_s2_sideband(prediction, vectors, ways, *, taken: int, strong: int, set_index: int):
    assert (prediction.meta["setIdx"], prediction.meta["bankMask"]) == (set_index, 8)
    assert len(prediction.micro_tage["result"]) == NUM_WAYS
    for vector in vectors:
        way, entry = matching_entry(prediction, vector.position, vector.branch_type)
        assert way == ways[vector.position]
        sideband = prediction.micro_tage["result"][way]
        assert sideband["valid"] == entry.valid == 1
        bits = sideband["bits"]
        # Whole-chip DefaultConfig forwards only taken/kind to MicroTage.
        # Position/action/strength are verified on the entry, meta and counter
        # state paths instead.
        assert (bits["attribute_branchType"], bits["taken"]) == (
            vector.branch_type, taken), (vector, prediction)


@pytest.mark.feature("BPU-ABTB-040")
async def test_four_way_microtage_sideband_tracks_interleaved_sets(abtb_agent):
    coverage = abtb_microtage_vector_coverage_model()
    await abtb_agent.reset()
    base = same_pc_position_vectors(3, 0)[:NUM_WAYS]
    mixed = tuple(
        replace(vector, branch_type=kind)
        for vector, kind in zip(base, (1, 2, 1, 3), strict=True)
    )
    conditional = tuple(replace(vector, target=vector.target + 0x1000) for vector in base)
    weak, weak_ways = await fill_taken_position_set(abtb_agent, mixed, path_hash=3)
    strong, strong_ways = await fill_taken_position_set(abtb_agent, conditional, path_hash=7)
    assert_s2_sideband(weak, mixed, weak_ways, taken=1, strong=0, set_index=0)

    # Two shared not-taken feedback beats move each conditional counter 2→1→0;
    # zero is a saturated negative bias. The other set is untouched.
    for _ in range(2):
        await train_conditional_direction(abtb_agent, conditional[0], strong, taken=0)
        strong = await abtb_agent.predict(base[0].pc, path_hash=7)
    assert_position_directions(strong, conditional, strong_ways, (0, 0, 0, 0))
    assert_s2_sideband(strong, conditional, strong_ways, taken=0, strong=1, set_index=1)

    profiles = (
        (3, mixed, weak_ways, 1, 0, 0, "mixed_weak"),
        (7, conditional, strong_ways, 0, 1, 1, "conditional_strong_negative"),
    ) * 3
    transfers = [
        abtb_agent.submit_predict(base[0].pc, path_hash=path_hash)
        for path_hash, *_ in profiles
    ]
    await abtb_agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(transfers), 2))
    for index, (transfer, profile) in enumerate(zip(transfers, profiles, strict=True)):
        _, vectors, ways, taken, strong_bias, set_index, label = profile
        observed = await transfer
        assert_s2_sideband(
            observed, vectors, ways, taken=taken,
            strong=strong_bias, set_index=set_index,
        )
        transition = "start" if index == 0 else (
            "weak_to_strong" if set_index == 1 else "strong_to_weak"
        )
        coverage.sample({"profile": label, "transition": transition})

    coverage.assert_coverage(100.0)
    write_abtb_microtage_vector_coverage(coverage, REPO_ROOT)
