"""MainBTB must not predict a branch before the current fetch start."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.checker.assertions import assert_filtered_raw_hit
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.mbtb.case.definitions import LATE_START_PC


@pytest.mark.feature("BPU-MBTB-009")
async def test_fetch_start_filters_earlier_branch_without_deleting_it(mbtb_agent):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, CONDITIONAL, cold.meta_entries)

    later_start = await mbtb_agent.predict(LATE_START_PC)
    assert_filtered_raw_hit(later_start, CONDITIONAL.position)

    from_block_start = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_vector_hit(from_block_start, CONDITIONAL)
