"""AheadBTB indirect-target correction."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import BranchVector
from suites.frontend.bpu.abtb.case.definitions import INDIRECT


@pytest.mark.feature("BPU-ABTB-004")
async def test_indirect_hit_updates_changed_target(abtb_agent):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(INDIRECT.pc)
    await train_taken(abtb_agent, INDIRECT, cold.meta)
    old = await abtb_agent.predict(INDIRECT.pc)
    assert_vector_hit(old, INDIRECT)
    changed = BranchVector(
        INDIRECT.pc,
        INDIRECT.target + 0x100,
        INDIRECT.position,
        INDIRECT.branch_type,
    )

    await train_taken(abtb_agent, changed, old.meta)

    assert_vector_hit(await abtb_agent.predict(changed.pc), changed)
