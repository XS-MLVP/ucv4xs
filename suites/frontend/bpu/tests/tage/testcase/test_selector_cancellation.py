"""Opposite branch feedback cancels in the shared TAGE selector."""

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


@pytest.mark.feature("BPU-TAGE-021")
async def test_opposite_selector_feedback_cancels_in_one_beat(tage_agent):
    await tage_agent.reset()
    coverage = tage_selector_coverage_model("cancel")
    earlier_position, later_position = await allocate_weak_pair_in_one_table(
        tage_agent, (1,) * 8, (1, 1)
    )
    earlier = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    later = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    provider_table = earlier.meta["providerTableIdx"]
    earlier_way = earlier.meta["providerWayIdx"]
    later_way = later.meta["providerWayIdx"]
    assert earlier_position < later_position
    assert later.meta["providerTableIdx"] == provider_table
    assert earlier_way != later_way
    assert (earlier.meta["providerTakenCtr_value"], later.meta["providerTakenCtr_value"]) == (4, 4)
    assert (earlier.meta["altConf"], later.meta["altConf"]) == (1, 1)
    assert (earlier.meta["useProvider"], later.meta["useProvider"]) == (0, 0)
    coverage.sample({"phase": "two_weak_ways"})

    # The earlier branch falls through, so its wrong weak provider votes for
    # the base. The later branch is taken, so its right weak provider votes
    # against the base. One valid FTQ beat must net those votes to zero.
    await tage_agent.train_batch(TageBatchTraining(PC, (
        TageBranchFeedback(earlier_position, 0, 0, earlier.meta, base_counter_value=0),
        None,
        TageBranchFeedback(
            later_position, 1, 0, later.meta,
            mispredict=1, base_counter_value=0,
        ),
    )))
    earlier = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    later = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert (earlier.meta["providerTableIdx"], later.meta["providerTableIdx"]) == (
        provider_table, provider_table
    )
    assert (earlier.meta["providerWayIdx"], later.meta["providerWayIdx"]) == (
        earlier_way, later_way
    )
    assert (earlier.meta["providerTakenCtr_value"], later.meta["providerTakenCtr_value"]) == (3, 5)
    assert (earlier.meta["providerUsefulCtr_value"], later.meta["providerUsefulCtr_value"]) == (0, 1)
    coverage.sample({"phase": "opposite_provider_writes"})

    # Restoring the two provider counters does not train the selector: the
    # first provider agrees with the base, the second is already strong.
    await tage_agent.train(TageTraining(
        PC, earlier_position, 1, 0, earlier.meta,
        mispredict=0, base_counter_value=0,
    ))
    await tage_agent.train(TageTraining(
        PC, later_position, 0, 0, later.meta,
        mispredict=0, base_counter_value=0,
    ))
    probe = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    weak_later = await tage_agent.predict(PC, later_position, 0, base_conf=1)
    assert (probe.meta["providerTakenCtr_value"], weak_later.meta["providerTakenCtr_value"]) == (4, 4)
    assert probe.meta["altConf"] == weak_later.meta["altConf"] == 1
    assert probe.meta["useProvider"] == 0
    assert probe.valid == 0
    coverage.sample({"phase": "net_zero_fallback"})

    # A single further provider-correct feedback now crosses the threshold.
    # An erroneous +1-only batch would still select the base at this point.
    await tage_agent.train(TageTraining(
        PC, later_position, 1, 0, weak_later.meta,
        mispredict=1, base_counter_value=0,
    ))
    selected = await tage_agent.predict(PC, earlier_position, 0, base_conf=1)
    assert selected.meta["providerTableIdx"] == provider_table
    assert selected.meta["providerWayIdx"] == earlier_way
    assert selected.meta["providerTakenCtr_value"] == 4
    assert selected.meta["useProvider"] == 1
    assert (selected.valid, selected.taken) == (1, 1)
    coverage.sample({"phase": "one_decrement_selects_provider"})

    coverage.assert_coverage(100.0)
    write_tage_selector_coverage(coverage, REPO_ROOT, "cancel")
