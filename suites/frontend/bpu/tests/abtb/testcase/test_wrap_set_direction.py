"""Physical set-index wrap must not alias adjacent counter cells."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_wrap_set_direction_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_wrap_set_direction_coverage
from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import highest_set_vectors
from bpuverify.abtb.case.definitions import wrapped_zero_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


BANKS = (1, 2)


@pytest.mark.feature("BPU-ABTB-033")
async def test_set_index_wrap_keeps_neighbor_counters_independent(abtb_agent):
    coverage = abtb_wrap_set_direction_coverage_model()
    await abtb_agent.reset()

    sentinels = {}
    residents = {}
    for bank in BANKS:
        sentinel = highest_set_vectors(bank, 1)[0]
        vectors = wrapped_zero_set_vectors(bank)
        assert vectors[0].pc == sentinel.pc + 2
        for set_index, set_vectors in ((63, (sentinel,)), (0, vectors)):
            for vector in set_vectors:
                cold = await abtb_agent.predict(vector.pc, path_hash=bank)
                assert_miss(cold)
                assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                    set_index, 1 << bank
                )
                await train_taken(abtb_agent, vector, cold.meta)
                observed = await assert_conditional_state(
                    abtb_agent, vector, taken=1, path_hash=bank
                )
                way, _ = matching_entry(
                    observed, vector.position, vector.branch_type
                )
                if set_index == 63:
                    sentinels[bank] = (vector, way)
                else:
                    key = (bank, way)
                    assert key not in residents
                    residents[key] = vector
        assert {way for resident_bank, way in residents if resident_bank == bank} == (
            set(range(NUM_WAYS))
        )

    for bank, (sentinel, _) in sentinels.items():
        sentinel_state = await assert_conditional_state(
            abtb_agent, sentinel, taken=1, path_hash=bank
        )
        await age_conditional_to_not_taken(
            abtb_agent, sentinel, sentinel_state, path_hash=bank
        )
    expected = {key: 1 for key in residents}

    async def assert_boundary_state() -> None:
        for bank, (sentinel, way) in sentinels.items():
            neighbor = await assert_conditional_state(
                abtb_agent, sentinel, taken=0, path_hash=bank
            )
            assert (neighbor.meta["setIdx"], neighbor.meta["bankMask"]) == (
                63, 1 << bank
            )
            assert sum(entry.valid for entry in neighbor.entries) == 1
            assert matching_entry(
                neighbor, sentinel.position, sentinel.branch_type
            )[0] == way
        for (bank, way), vector in residents.items():
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=expected[(bank, way)], path_hash=bank
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                0, 1 << bank
            )
            # Four resident tags share the SRAM set, but a lookup matches
            # exactly one tag rather than returning all four entries.
            assert sum(entry.valid for entry in observed.entries) == 1
            assert matching_entry(
                observed, vector.position, vector.branch_type
            )[0] == way

    await assert_boundary_state()
    for (bank, way), vector in residents.items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=bank
        )
        current = await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=bank
        )
        expected[(bank, way)] = 0
        await assert_boundary_state()
        coverage.sample({
            "set_0_transition": f"bank_{bank}_way_{way}_negative",
            "edge_neighbor": "set_63_preserved",
            "other_bank": f"bank_{bank}_with_neighbor_stable",
        })

        for direction in (0, 1, 1, 1):
            await train_conditional_direction(
                abtb_agent, vector, current, taken=1
            )
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=bank
            )
        expected[(bank, way)] = 1
        await assert_boundary_state()
        coverage.sample({
            "set_0_transition": f"bank_{bank}_way_{way}_positive",
            "edge_neighbor": "set_63_preserved",
            "other_bank": f"bank_{bank}_with_neighbor_stable",
        })

    coverage.assert_coverage(100.0)
    write_abtb_wrap_set_direction_coverage(coverage, REPO_ROOT)
