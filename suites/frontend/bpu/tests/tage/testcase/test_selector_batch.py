"""Exercise the shared alternate selector with two independent TAGE ways."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_selector_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_selector_coverage
from suites.frontend.bpu.tage.checker.assertions import allocate_weak_pair_in_one_table
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-TAGE-020")
async def test_two_branch_feedback_takes_two_selector_steps(tage_agent):
    await tage_agent.reset()
    coverage = tage_selector_coverage_model("batch")
    earlier_position, later_position = await allocate_weak_pair_in_one_table(
        tage_agent, tuple(position % 2 for position in range(32)), (1, 0)
    )
    earlier = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    later = await tage_agent.predict(PC, later_position, 1, base_conf=1)
    earlier_way = earlier.meta["providerWayIdx"]
    later_way = later.meta["providerWayIdx"]
    assert earlier_position < later_position
    assert earlier.meta["providerTableIdx"] == later.meta["providerTableIdx"]
    assert earlier_way != later_way
    assert (earlier.meta["providerTakenCtr_value"], later.meta["providerTakenCtr_value"]) == (4, 3)
    assert (earlier.meta["altConf"], later.meta["altConf"]) == (1, 1)
    assert (earlier.meta["useProvider"], later.meta["useProvider"]) == (0, 0)
    coverage.sample({"phase": "two_weak_ways"})

    # Both base directions are right and both weak providers disagree: the
    # earlier branch falls through and the later one is taken. Their distinct
    # ways must both be written while the selector takes two increments.
    await tage_agent.train_batch(TageBatchTraining(PC, (
        TageBranchFeedback(earlier_position, 0, 0, earlier.meta, base_counter_value=0),
        None,
        TageBranchFeedback(later_position, 1, 1, later.meta, base_counter_value=3),
    )))
    earlier = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    later = await tage_agent.predict(PC, later_position, 1, base_conf=1)
    assert (earlier.meta["providerWayIdx"], later.meta["providerWayIdx"]) == (earlier_way, later_way)
    assert (earlier.meta["providerTakenCtr_value"], later.meta["providerTakenCtr_value"]) == (3, 4)
    coverage.sample({"phase": "two_provider_writes"})

    # Provider counters remain weak but have flipped direction. Change the
    # supplied base directions for the next predictions; the selector bucket
    # stays the same because both bases remain high-confidence.
    earlier = await tage_agent.predict(PC, earlier_position, 1, base_conf=1)
    later = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert (earlier.meta["providerTakenCtr_value"], later.meta["providerTakenCtr_value"]) == (3, 4)
    assert (earlier.meta["useProvider"], later.meta["useProvider"]) == (0, 0)
    coverage.sample({"phase": "weak_after_batch"})

    # A single decrement after the batch must not cross the selector's
    # positive threshold. Both decrements together still leave it positive
    # only if the batch truly supplied *two* increments.
    await tage_agent.train(TageTraining(
        PC, earlier_position, 0, 1, earlier.meta,
        mispredict=1, base_counter_value=3,
    ))
    probe = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert probe.meta["providerTakenCtr_value"] == 4
    assert probe.meta["useProvider"] == 0
    coverage.sample({"phase": "one_decrement"})

    await tage_agent.train(TageTraining(
        PC, later_position, 1, 0, probe.meta,
        mispredict=1, base_counter_value=0,
    ))
    strong_later = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert strong_later.meta["providerTakenCtr_value"] == 5
    await tage_agent.train(TageTraining(
        PC, later_position, 0, 0, strong_later.meta,
        mispredict=0, base_counter_value=0,
    ))
    probe = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert probe.meta["providerTakenCtr_value"] == 4
    assert probe.meta["useProvider"] == 0
    coverage.sample({"phase": "two_decrements"})

    strong_earlier = await tage_agent.predict(PC, earlier_position, 1, base_conf=1)
    assert strong_earlier.meta["providerTakenCtr_value"] == 2
    await tage_agent.train(TageTraining(
        PC, earlier_position, 1, 1, strong_earlier.meta,
        mispredict=0, base_counter_value=3,
    ))
    weak_earlier = await tage_agent.predict(PC, earlier_position, 1, base_conf=1)
    assert weak_earlier.meta["providerTakenCtr_value"] == 3
    await tage_agent.train(TageTraining(
        PC, earlier_position, 0, 1, weak_earlier.meta,
        mispredict=1, base_counter_value=3,
    ))
    selected = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert selected.meta["providerTakenCtr_value"] == 4
    assert selected.meta["useProvider"] == 1
    assert (selected.valid, selected.taken) == (1, 1)
    coverage.sample({"phase": "third_decrement_selects_provider"})

    coverage.assert_coverage(100.0)
    write_tage_selector_coverage(coverage, REPO_ROOT, "batch")
