"""MainBTB functional coverage sampled after observed checks."""

from __future__ import annotations

from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_coverage
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_filtered_raw_hit
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_counter
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BRANCH_TYPES
from suites.frontend.bpu.mbtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.mbtb.case.definitions import DIRECT
from suites.frontend.bpu.mbtb.case.definitions import INDIRECT
from suites.frontend.bpu.mbtb.case.definitions import LATE_START_PC
from suites.frontend.bpu.mbtb.case.definitions import NEXT_PAGE_BRANCH
from suites.frontend.bpu.mbtb.case.definitions import PAGE_END_PC
from suites.frontend.bpu.mbtb.case.definitions import VISIBLE_NEXT_PAGE_BRANCH
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.enable_scenarios import observe_lookup_gate
from suites.frontend.bpu.mbtb.case.enable_scenarios import observe_training_gate
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_mbtb_functional_coverage_closes_defined_bins(mbtb_agent):
    coverage = mbtb_coverage_model()
    await mbtb_agent.reset()
    prediction = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_miss(prediction)
    coverage.sample({
        "branch_type": 0,
        "occupancy": 0,
        "operation": "cold",
        "counter": "not_sampled",
    })

    for vector in BRANCH_TYPES:
        await train(mbtb_agent, vector, prediction.meta_entries)
        prediction = await mbtb_agent.predict(vector.pc)
        assert_vector_hit(prediction, vector)
        coverage.sample({
            "branch_type": vector.branch_type,
            "occupancy": sum(entry.valid for entry in prediction.entries),
            "operation": "allocate",
            "counter": "not_sampled",
        })

    changed = BranchVector(
        INDIRECT.pc, INDIRECT.target + 0x200, INDIRECT.position, INDIRECT.branch_type
    )
    await train(mbtb_agent, changed, prediction.meta_entries)
    prediction = await mbtb_agent.predict(changed.pc)
    assert_vector_hit(prediction, changed)
    coverage.sample({
        "branch_type": changed.branch_type,
        "occupancy": sum(entry.valid for entry in prediction.entries),
        "operation": "target_update",
        "counter": "not_sampled",
    })

    for taken, label, terminal in (
        (0, "not_taken_saturated", 0),
        (1, "taken_saturated", 3),
    ):
        for _ in range(5):
            await train(
                mbtb_agent, CONDITIONAL, prediction.meta_entries, taken=taken
            )
            prediction = await mbtb_agent.predict(CONDITIONAL.pc)
        assert matching_counter(prediction, CONDITIONAL) == terminal
        coverage.sample({
            "branch_type": CONDITIONAL.branch_type,
            "occupancy": sum(entry.valid for entry in prediction.entries),
            "operation": "counter_train",
            "counter": label,
        })

    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(PAGE_END_PC)
    assert_miss(cold)
    await train(mbtb_agent, NEXT_PAGE_BRANCH, cold.meta_entries)
    filtered = await mbtb_agent.predict(PAGE_END_PC)
    assert_filtered_raw_hit(filtered, NEXT_PAGE_BRANCH.position)
    visible = await mbtb_agent.predict(VISIBLE_NEXT_PAGE_BRANCH.pc)
    assert_vector_hit(visible, VISIBLE_NEXT_PAGE_BRANCH)
    coverage.sample({
        "branch_type": VISIBLE_NEXT_PAGE_BRANCH.branch_type,
        "occupancy": sum(entry.valid for entry in visible.entries),
        "operation": "cross_page_filter",
        "counter": "not_sampled",
    })

    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_miss(cold)
    await train(mbtb_agent, CONDITIONAL, cold.meta_entries)
    filtered = await mbtb_agent.predict(LATE_START_PC)
    assert_filtered_raw_hit(filtered, CONDITIONAL.position)
    visible = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_vector_hit(visible, CONDITIONAL)
    coverage.sample({
        "branch_type": CONDITIONAL.branch_type,
        "occupancy": sum(entry.valid for entry in visible.entries),
        "operation": "prefix_filter",
        "counter": "not_sampled",
    })

    lookup_gate = await observe_lookup_gate(mbtb_agent)
    assert_miss(lookup_gate.held)
    assert lookup_gate.disabled == lookup_gate.held, lookup_gate
    assert not any(
        item["rawHit"]
        for bank in lookup_gate.disabled.meta_entries
        for item in bank
    ), lookup_gate
    assert_vector_hit(lookup_gate.restored, DIRECT)
    coverage.sample({
        "branch_type": DIRECT.branch_type,
        "occupancy": sum(entry.valid for entry in lookup_gate.restored.entries),
        "operation": "lookup_disabled",
        "counter": "not_sampled",
    })

    training_gate = await observe_training_gate(mbtb_agent)
    assert_vector_hit(training_gate.disabled_update, INDIRECT)
    assert_vector_hit(training_gate.enabled_update, training_gate.changed)
    coverage.sample({
        "branch_type": training_gate.changed.branch_type,
        "occupancy": sum(
            entry.valid for entry in training_gate.enabled_update.entries
        ),
        "operation": "training_disabled",
        "counter": "not_sampled",
    })

    coverage.assert_coverage(100.0)
    write_mbtb_coverage(coverage, REPO_ROOT)
