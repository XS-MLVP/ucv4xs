"""Counter and tag isolation across the physical set-31/32 boundary."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_middle_boundary_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_middle_boundary_coverage
from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import middle_boundary_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-027")
async def test_middle_set_boundary_preserves_bank_way_counter_isolation(abtb_agent):
    await abtb_agent.reset()
    coverage = abtb_middle_boundary_coverage_model()
    residents = {}

    for set_index in (31, 32):
        for bank in range(4):
            for vector in middle_boundary_vectors(set_index, bank):
                cold = await abtb_agent.predict(vector.pc, path_hash=bank)
                assert_miss(cold)
                assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                    set_index, 1 << bank
                )
                await train_taken(abtb_agent, vector, cold.meta)
                trained = await assert_conditional_state(
                    abtb_agent, vector, taken=1, path_hash=bank
                )
                way, _ = matching_entry(trained, vector.position, 1)
                key = (set_index, bank, way)
                assert key not in residents
                residents[key] = vector

    assert set(residents) == {
        (set_index, bank, way)
        for set_index in (31, 32)
        for bank in range(4)
        for way in range(NUM_WAYS)
    }
    expected = {key: 1 for key in residents}

    async def assert_all_residents() -> None:
        for (set_index, bank, way), vector in residents.items():
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=expected[(set_index, bank, way)],
                path_hash=bank,
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank
            )

    await assert_all_residents()
    for (set_index, bank, way), vector in residents.items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=bank
        )
        current = await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=bank
        )
        expected[(set_index, bank, way)] = 0
        await assert_all_residents()
        coverage.sample({"cell_transition": f"set_{set_index}_bank_{bank}_way_{way}_negative"})

        for direction in (0, 1, 1, 1):
            await train_conditional_direction(
                abtb_agent, vector, current, taken=1
            )
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=bank
            )
        expected[(set_index, bank, way)] = 1
        await assert_all_residents()
        coverage.sample({"cell_transition": f"set_{set_index}_bank_{bank}_way_{way}_positive"})

    coverage.assert_coverage(100.0)
    write_abtb_middle_boundary_coverage(coverage, REPO_ROOT)
