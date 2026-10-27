"""MicroBTB enable gates both fastTrain writes and prediction visibility."""

from __future__ import annotations

import pytest

from bpuverify.ubtb.coverage.catalog import ubtb_enable_coverage_model
from bpuverify.ubtb.coverage.catalog import write_ubtb_enable_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.checker.assertions import assert_miss
from bpuverify.ubtb.checker.assertions import expected_prediction
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import BranchVector
from bpuverify.ubtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-UBTB-014")
async def test_global_disable_blocks_fast_train_without_erasing_entry(ubtb_agent):
    coverage = ubtb_enable_coverage_model()
    await ubtb_agent.reset()
    await assert_miss(ubtb_agent, DIRECT.pc)

    await ubtb_agent.set_enabled(False)
    await train_taken(ubtb_agent, DIRECT)
    await ubtb_agent.set_enabled(True)
    await assert_miss(ubtb_agent, DIRECT.pc)
    coverage.sample({"phase": "disabled_allocate_blocked"})

    await train_taken(ubtb_agent, DIRECT)
    await assert_hit(ubtb_agent, DIRECT)
    coverage.sample({"phase": "enabled_allocate"})

    changed = BranchVector(DIRECT.pc, DIRECT.target + 0x100, 7, 3)
    await ubtb_agent.set_enabled(False)
    for _ in range(4):
        await train_taken(ubtb_agent, changed)
    await ubtb_agent.set_enabled(True)
    await assert_hit(ubtb_agent, DIRECT)
    coverage.sample({"phase": "disabled_update_blocked"})

    await ubtb_agent.set_enabled(False)
    await assert_miss(ubtb_agent, DIRECT.pc)
    coverage.sample({"phase": "disabled_lookup_hidden"})
    await ubtb_agent.set_enabled(True)
    await assert_hit(ubtb_agent, DIRECT)
    coverage.sample({"phase": "reenabled_hit_retained"})

    for _ in range(4):
        await train_taken(ubtb_agent, changed)
        if await ubtb_agent.predict(DIRECT.pc) == expected_prediction(changed):
            break
    assert await ubtb_agent.predict(DIRECT.pc) == expected_prediction(changed)
    coverage.sample({"phase": "enabled_update"})
    coverage.assert_coverage(100.0)
    write_ubtb_enable_coverage(coverage, REPO_ROOT)
