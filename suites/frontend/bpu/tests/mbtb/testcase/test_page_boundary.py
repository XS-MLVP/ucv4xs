"""MainBTB filters a cross-page fetch without losing the next page's entry."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.checker.assertions import assert_filtered_raw_hit
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import NEXT_PAGE_BRANCH
from suites.frontend.bpu.mbtb.case.definitions import PAGE_END_PC
from suites.frontend.bpu.mbtb.case.definitions import VISIBLE_NEXT_PAGE_BRANCH


@pytest.mark.feature("BPU-MBTB-008")
async def test_cross_page_prediction_is_filtered_but_entry_remains(mbtb_agent):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(PAGE_END_PC)
    assert_miss(cold)
    await train(mbtb_agent, NEXT_PAGE_BRANCH, cold.meta_entries)

    near_page_end = await mbtb_agent.predict(PAGE_END_PC)
    assert_filtered_raw_hit(near_page_end, NEXT_PAGE_BRANCH.position)

    from_next_page = await mbtb_agent.predict(VISIBLE_NEXT_PAGE_BRANCH.pc)
    assert_vector_hit(from_next_page, VISIBLE_NEXT_PAGE_BRANCH)
