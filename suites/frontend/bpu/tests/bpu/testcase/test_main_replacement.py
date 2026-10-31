"""Integrated semantic intent; no clock edges, tasks, gathers or raw writes."""
import pytest

from suites.frontend.bpu.bpu.case.main_replacement import check_main_replacement
from suites.frontend.bpu.mbtb.coverage.replacement_overlap import ReplacementCoverage
from suites.frontend.bpu.mbtb.model.replacement_overlap import CASES


@pytest.mark.feature('BPU-INT-097')
@pytest.mark.parametrize('mode',CASES)
async def test_original_feedback_latest_age_selects_victim_and_preserves_all_survivors(bpu_agent,bpu_sc_output,mode):
    coverage=ReplacementCoverage(mode,scope='bpu')
    try:await check_main_replacement(bpu_agent,coverage,mode)
    finally:coverage.write(bpu_sc_output)
