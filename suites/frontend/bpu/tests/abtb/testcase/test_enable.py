"""AheadBTB global enable gates both training and prediction."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_enable_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_enable_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.abtb.case.definitions import INDIRECT
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-031")
async def test_global_disable_blocks_training_without_erasing_entry(abtb_agent):
    coverage = abtb_enable_coverage_model()
    await abtb_agent.reset()
    cold = await abtb_agent.predict(INDIRECT.pc)
    assert_miss(cold)

    await abtb_agent.set_enabled(False)
    await train_taken(abtb_agent, INDIRECT, cold.meta)
    await abtb_agent.set_enabled(True)
    assert_miss(await abtb_agent.predict(INDIRECT.pc))
    coverage.sample({"phase": "disabled_allocate_blocked"})

    await train_taken(abtb_agent, INDIRECT, cold.meta)
    trained = await abtb_agent.predict(INDIRECT.pc)
    assert_vector_hit(trained, INDIRECT)
    coverage.sample({"phase": "enabled_allocate"})

    await abtb_agent.set_enabled(False)
    hidden = await abtb_agent.predict(INDIRECT.pc)
    assert_miss(hidden)
    assert hidden.meta["valid"] == 0, hidden
    coverage.sample({"phase": "disabled_lookup_hidden"})
    await abtb_agent.set_enabled(True)
    assert_vector_hit(await abtb_agent.predict(INDIRECT.pc), INDIRECT)
    coverage.sample({"phase": "reenabled_hit_retained"})

    changed = BranchVector(
        INDIRECT.pc, INDIRECT.target + 0x100, INDIRECT.position, INDIRECT.branch_type
    )
    await abtb_agent.set_enabled(False)
    await train_taken(abtb_agent, changed, trained.meta)
    await abtb_agent.set_enabled(True)
    assert_vector_hit(await abtb_agent.predict(INDIRECT.pc), INDIRECT)
    coverage.sample({"phase": "disabled_update_blocked"})

    await train_taken(abtb_agent, changed, trained.meta)
    assert_vector_hit(await abtb_agent.predict(INDIRECT.pc), changed)
    coverage.sample({"phase": "enabled_update"})
    coverage.assert_coverage(100.0)
    write_abtb_enable_coverage(coverage, REPO_ROOT)
