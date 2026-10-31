"""Four history banks keep both neighboring sets stable around set 3."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_three_set_neighborhood_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_three_set_neighborhood_coverage
from suites.frontend.bpu.abtb.checker.assertions import age_conditional_to_not_taken
from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.definitions import three_set_neighborhood_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


BANKS = range(4)
CENTER_SET = 3
FLANK_SETS = (2, 4)


@pytest.mark.feature("BPU-ABTB-043")
async def test_center_set_counters_leave_both_flanks_unchanged(abtb_agent):
    coverage = abtb_three_set_neighborhood_coverage_model()
    await abtb_agent.reset()
    sentinels = {}
    center = {}

    for bank in BANKS:
        for set_index in (2, CENTER_SET, 4):
            count = NUM_WAYS if set_index == CENTER_SET else 1
            for vector in three_set_neighborhood_vectors(bank, set_index, count):
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
                if set_index == CENTER_SET:
                    key = (bank, way)
                    assert key not in center
                    center[key] = vector
                else:
                    sentinels[(bank, set_index)] = (vector, way)
        assert {way for resident_bank, way in center if resident_bank == bank} == (
            set(range(NUM_WAYS))
        )

    assert set(sentinels) == {
        (bank, set_index) for bank in BANKS for set_index in FLANK_SETS
    }
    for (bank, _), (vector, _) in sentinels.items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=bank
        )
        await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=bank
        )
    expected = {key: 1 for key in center}

    async def assert_neighborhood() -> None:
        for (bank, set_index), (vector, way) in sentinels.items():
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=0, path_hash=bank
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            assert sum(entry.valid for entry in observed.entries) == 1
            assert matching_entry(
                observed, vector.position, vector.branch_type
            )[0] == way
        for (bank, way), vector in center.items():
            observed = await assert_conditional_state(
                abtb_agent, vector, taken=expected[(bank, way)], path_hash=bank
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                CENTER_SET, 1 << bank
            )
            assert sum(entry.valid for entry in observed.entries) == 1
            assert matching_entry(
                observed, vector.position, vector.branch_type
            )[0] == way

    await assert_neighborhood()
    for (bank, way), vector in center.items():
        current = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=bank
        )
        current = await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=bank
        )
        expected[(bank, way)] = 0
        await assert_neighborhood()
        coverage.sample({
            "cell_transition": f"bank_{bank}_way_{way}_negative",
            "flanks": "both_preserved",
            "active_bank": bank,
        })

        for direction in (0, 1, 1, 1):
            await train_conditional_direction(abtb_agent, vector, current, taken=1)
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=bank
            )
        expected[(bank, way)] = 1
        await assert_neighborhood()
        coverage.sample({
            "cell_transition": f"bank_{bank}_way_{way}_positive",
            "flanks": "both_preserved",
            "active_bank": bank,
        })

    coverage.assert_coverage(100.0)
    write_abtb_three_set_neighborhood_coverage(coverage, REPO_ROOT)
