"""Selector feedback across tags and high-confidence provider depths."""

from __future__ import annotations

import pytest

from bpuverify.common.model.configuration import TAGE_TABLES, POSITIONS
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.catalog import tage_selector_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_selector_coverage
from bpuverify.tage.case.definitions import PC
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.tage.checker.assertions import await_cold_allocation


@pytest.mark.feature("BPU-TAGE-013")
async def test_selector_feedback_changes_an_untouched_weak_tag(tage_agent):
    await tage_agent.reset()
    coverage = tage_selector_coverage_model("cross_tag")
    weak_by_position = {}
    trainer_position = None
    for position in range(POSITIONS):
        cold = await tage_agent.predict(PC, position, 0, base_conf=1)
        assert cold.meta["hasProvider"] == 0
        await tage_agent.train(TageTraining(PC, position, 1, 0, cold.meta))
        weak = await tage_agent.predict(PC, position, 0, base_conf=1)
        assert weak.meta["hasProvider"] == 1
        assert weak.meta["providerTakenCtr_value"] == 4
        assert weak.meta["altConf"] == 1
        assert weak.meta["useProvider"] == 0
        assert weak.valid == 0
        weak_by_position[position] = weak
        if position and weak.meta["providerTableIdx"] == weak_by_position[0].meta["providerTableIdx"]:
            trainer_position = position
            break
    assert trainer_position is not None, "no second provider at the probe's depth"
    before = await tage_agent.predict(PC, 0, 0, base_conf=1)
    assert before.meta["providerTakenCtr_value"] == 4
    assert before.meta["altConf"] == 1
    assert before.meta["useProvider"] == 0
    assert before.valid == 0
    coverage.sample({"selection": "base_fallback", "probe_counter": 4})

    # A weak taken provider is right while the base fallback is wrong. RTL
    # trains the shared selector but explicitly suppresses new allocation.
    await tage_agent.train(TageTraining(PC, trainer_position, 1, 0, weak_by_position[trainer_position].meta, mispredict=1, base_counter_value=0))
    after = await tage_agent.predict(PC, 0, 0, base_conf=1)
    assert after.meta["providerTableIdx"] == before.meta["providerTableIdx"]
    assert after.meta["providerWayIdx"] == before.meta["providerWayIdx"]
    assert after.meta["providerTakenCtr_value"] == 4
    assert after.meta["altConf"] == 1
    assert after.meta["useProvider"] == 1
    assert after.valid == 1 and after.taken == 1
    trainer = await tage_agent.predict(PC, trainer_position, 0, base_conf=1)
    assert trainer.meta["providerTableIdx"] == before.meta["providerTableIdx"]
    assert trainer.meta["providerTakenCtr_value"] == 5
    coverage.sample({"selection": "provider", "probe_counter": 4})
    coverage.assert_coverage(100.0)
    write_tage_selector_coverage(coverage, REPO_ROOT, "cross-tag")


@pytest.mark.feature("BPU-TAGE-014")
async def test_high_confidence_feedback_across_all_provider_depths(tage_agent):
    await tage_agent.reset()
    coverage = tage_selector_coverage_model("depth")
    seen_depths = set()

    # Distinct tags use reset-derived LFSR opportunities at all eight depths.
    # Every selected table and way is checked against the independent plan.
    for position in range(TAGE_TABLES):
        cold = await tage_agent.predict(PC, position, 0, base_conf=1)
        assert cold.meta["hasProvider"] == 0
        desired = await await_cold_allocation(tage_agent, pc=PC, position=position, taken=1, base=0, table=position)
        await tage_agent.train(TageTraining(PC, position, 1, 0, cold.meta))
        weak = await tage_agent.predict(PC, position, 0, base_conf=1)
        depth = weak.meta["providerTableIdx"]
        assert (depth, weak.meta["providerWayIdx"]) == desired
        assert weak.meta["hasProvider"] == 1
        assert weak.meta["providerTakenCtr_value"] == 4
        assert weak.meta["altConf"] == 1
        assert weak.meta["useProvider"] == 0
        assert weak.valid == 0

        for expected_counter in (3, 2):
            # The high-confidence not-taken base is correct, so no
            # misprediction/extra allocation is attributed to this feedback.
            await tage_agent.train(TageTraining(
                PC, position, 0, 0, weak.meta,
                mispredict=0, base_counter_value=0,
            ))
            weak = await tage_agent.predict(PC, position, 0, base_conf=1)
            assert weak.meta["hasProvider"] == 1
            assert weak.meta["providerTableIdx"] == depth
            assert weak.meta["providerTakenCtr_value"] == expected_counter
            assert weak.meta["altConf"] == 1
            assert weak.meta["useProvider"] == int(expected_counter == 2)
            assert weak.valid == int(expected_counter == 2)

        seen_depths.add(depth)
        coverage.sample({"provider_depth": depth})
        if seen_depths == set(range(TAGE_TABLES)):
            break

    assert seen_depths == set(range(TAGE_TABLES))
    coverage.assert_coverage(100.0)
    write_tage_selector_coverage(coverage, REPO_ROOT, "depth")
