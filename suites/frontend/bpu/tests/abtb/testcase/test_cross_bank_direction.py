"""History-selected banks isolate four-way same-PC direction feedback."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_cross_bank_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_cross_bank_direction_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_directions
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


PHYSICAL_SET = 1
BANKS = range(4)


@pytest.mark.feature("BPU-ABTB-041")
async def test_same_pc_four_way_directions_are_isolated_across_hash_banks(abtb_agent):
    coverage = abtb_cross_bank_direction_coverage_model()
    await abtb_agent.reset()
    vectors = {
        bank: same_pc_position_vectors(bank, PHYSICAL_SET)[:NUM_WAYS]
        for bank in BANKS
    }
    assert len({branch.pc for group in vectors.values() for branch in group}) == 1
    pc = vectors[0][0].pc
    way_by_position = {}

    for bank in BANKS:
        cold = await abtb_agent.predict(pc, path_hash=bank)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
            PHYSICAL_SET, 1 << bank,
        )
        full, ways = await fill_taken_position_set(
            abtb_agent, vectors[bank], path_hash=bank
        )
        assert (full.meta["setIdx"], full.meta["bankMask"]) == (
            PHYSICAL_SET, 1 << bank,
        )
        way_by_position[bank] = ways

    expected = {bank: (1,) * NUM_WAYS for bank in BANKS}

    async def assert_all_bank_profiles() -> None:
        for observed_bank in BANKS:
            prediction = await abtb_agent.predict(pc, path_hash=observed_bank)
            assert (prediction.meta["setIdx"], prediction.meta["bankMask"]) == (
                PHYSICAL_SET, 1 << observed_bank,
            )
            assert_position_directions(
                prediction,
                vectors[observed_bank],
                way_by_position[observed_bank],
                expected[observed_bank],
            )

    await assert_all_bank_profiles()
    for bank in BANKS:
        current = await abtb_agent.predict(pc, path_hash=bank)
        await train_conditional_direction(
            abtb_agent, vectors[bank][0], current, taken=0
        )
        expected[bank] = (0,) * NUM_WAYS
        await assert_all_bank_profiles()
        coverage.sample({"transition": f"bank_{bank}_aged"})

        for position_index, branch in enumerate(vectors[bank]):
            current = await abtb_agent.predict(pc, path_hash=bank)
            await train_taken(abtb_agent, branch, current.meta)
            expected[bank] = tuple(
                int(index == position_index) for index in range(NUM_WAYS)
            )
            await assert_all_bank_profiles()
            way = way_by_position[bank][branch.position]
            coverage.sample({"transition": f"bank_{bank}_way_{way}_recovered"})

    coverage.assert_coverage(100.0)
    write_abtb_cross_bank_direction_coverage(coverage, REPO_ROOT)
