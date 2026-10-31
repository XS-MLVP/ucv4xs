"""MainBTB indirect entry correction and isolation."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.definitions import INDIRECT


@pytest.mark.feature("BPU-MBTB-005")
async def test_indirect_target_update_reuses_existing_entry(mbtb_agent):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(INDIRECT.pc)
    await train(mbtb_agent, INDIRECT, cold.meta_entries)
    old = await mbtb_agent.predict(INDIRECT.pc)
    changed = BranchVector(
        INDIRECT.pc,
        INDIRECT.target + 0x200,
        INDIRECT.position,
        INDIRECT.branch_type,
    )

    await train(mbtb_agent, changed, old.meta_entries)
    updated = await mbtb_agent.predict(changed.pc)

    assert_vector_hit(updated, changed)
    assert sum(entry.valid for entry in updated.entries) == 1
