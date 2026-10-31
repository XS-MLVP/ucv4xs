"""Recover surviving and replacement counters with two aged flanking sets."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_flanked_recovery_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_flanked_recovery_coverage
from suites.frontend.bpu.abtb.checker.assertions import age_conditional_to_not_taken
from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.abtb.case.flanked_scenario import AgedFlankedSet
from suites.frontend.bpu.abtb.case.flanked_scenario import BANKS
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-045")
async def test_recover_every_way_after_aged_replacement_with_two_flanks(abtb_agent):
    coverage = abtb_flanked_recovery_coverage_model()
    state = await AgedFlankedSet.prepare(abtb_agent)
    replacements = set()
    for bank in BANKS:
        victim_way, _ = await state.replace_bank(bank)
        replacements.add((bank, victim_way))
    assert len(replacements) == len(BANKS)
    assert len(state.center) == len(BANKS) * NUM_WAYS
    assert {key for key, taken in state.expected_taken.items() if taken} == replacements

    # Survivors are already negative. Re-age each new replacement separately:
    # its initial taken output alone does not prove that the new tag can later
    # decrement and recover through the physical victim's counter path.
    for (bank, way), vector in tuple(state.center.items()):
        key = (bank, way)
        origin = "replacement" if key in replacements else "survivor"
        current = await assert_conditional_state(
            abtb_agent, vector, taken=state.expected_taken[key], path_hash=bank
        )
        if origin == "replacement":
            current = await age_conditional_to_not_taken(
                abtb_agent, vector, current, path_hash=bank
            )
            state.expected_taken[key] = 0
            await state.assert_neighborhood()
        for direction in (0, 1, 1, 1):
            await train_conditional_direction(abtb_agent, vector, current, taken=1)
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=bank
            )
        state.expected_taken[key] = 1
        await state.assert_neighborhood()
        coverage.sample({
            "recovered_cell": f"bank_{bank}_way_{way}",
            "entry_origin": origin,
            "isolation": "both_flanks_and_peers",
        })

    coverage.assert_coverage(100.0)
    write_abtb_flanked_recovery_coverage(coverage, REPO_ROOT)
