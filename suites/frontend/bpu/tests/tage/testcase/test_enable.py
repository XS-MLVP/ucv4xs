"""TAGE enable gates both training and use while retaining learned entries."""

from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.catalog import tage_enable_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_enable_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-015")
async def test_global_enable_blocks_training_and_masks_provider(tage_agent):
    coverage = tage_enable_coverage_model()
    await tage_agent.reset()
    cold = await tage_agent.predict(PC, POSITION, 0)
    assert cold.meta["hasProvider"] == 0
    allocation = TageTraining(PC, POSITION, 1, 0, cold.meta)

    await tage_agent.set_enabled(False)
    await tage_agent.train(allocation)
    await tage_agent.set_enabled(True)
    still_cold = await tage_agent.predict(PC, POSITION, 0)
    assert still_cold.meta["hasProvider"] == 0
    coverage.sample({"phase": "disabled_train_blocked"})

    await tage_agent.train(allocation)
    allocated = await tage_agent.predict(PC, POSITION, 0)
    assert allocated.meta["hasProvider"] == 1
    coverage.sample({"phase": "enabled_train_allocates"})

    await tage_agent.set_enabled(False)
    hidden = await tage_agent.predict(PC, POSITION, 0)
    assert hidden.valid == 0
    assert hidden.provider_counter_valid == 0
    coverage.sample({"phase": "disabled_lookup_hidden"})

    await tage_agent.set_enabled(True)
    retained = await tage_agent.predict(PC, POSITION, 0)
    assert retained.meta["hasProvider"] == 1
    assert retained.meta["providerTableIdx"] == allocated.meta["providerTableIdx"]
    assert retained.meta["providerWayIdx"] == allocated.meta["providerWayIdx"]
    coverage.sample({"phase": "reenabled_provider_retained"})
    coverage.assert_coverage(100.0)
    write_tage_enable_coverage(coverage, REPO_ROOT)
