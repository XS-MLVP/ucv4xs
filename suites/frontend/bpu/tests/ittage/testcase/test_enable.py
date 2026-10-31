"""ITTAGE global disable must suppress training without erasing providers."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.coverage.catalog import ittage_enable_coverage_model
from suites.frontend.bpu.ittage.coverage.catalog import write_ittage_enable_coverage
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ITTAGE-011")
async def test_global_disable_blocks_training_and_retains_provider(ittage_agent):
    coverage = ittage_enable_coverage_model()
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0
    allocation = IttageTraining(PC, POSITION, TARGET_A, cold.meta, 1)

    await ittage_agent.set_enabled(False)
    await ittage_agent.train(allocation)
    await ittage_agent.set_enabled(True)
    still_cold = await ittage_agent.predict(PC)
    assert still_cold.hit == 0
    coverage.sample({"phase": "disabled_train_blocked"})

    await ittage_agent.train(allocation)
    allocated = await ittage_agent.predict(PC)
    assert (allocated.hit, allocated.target) == (1, TARGET_A)
    coverage.sample({"phase": "enabled_train_allocates"})

    await ittage_agent.set_enabled(False)
    hidden = await ittage_agent.predict(PC)
    assert hidden.hit == 0
    coverage.sample({"phase": "disabled_lookup_hidden"})

    await ittage_agent.set_enabled(True)
    retained = await ittage_agent.predict(PC)
    assert (retained.hit, retained.target) == (1, TARGET_A)
    coverage.sample({"phase": "reenabled_hit_retained"})
    coverage.assert_coverage(100.0)
    write_ittage_enable_coverage(coverage, REPO_ROOT)
