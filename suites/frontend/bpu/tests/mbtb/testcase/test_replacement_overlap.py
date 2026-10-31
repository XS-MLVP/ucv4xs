"""Only semantic intent; agent owns inputs, monitors and pipeline completion."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.mbtb.case.replacement_overlap import check_replacement_overlap
from suites.frontend.bpu.mbtb.coverage.replacement_overlap import ReplacementCoverage
from suites.frontend.bpu.mbtb.model.replacement_overlap import CASES


@pytest.mark.feature('BPU-MBTB-030')
@pytest.mark.parametrize('mode',CASES)
async def test_latest_age_controls_next_allocation_without_cross_context_touch(mbtb_agent,mode):
    coverage=ReplacementCoverage(mode)
    try:await check_replacement_overlap(mbtb_agent,coverage,mode)
    finally:coverage.write(output_directory(REPO_ROOT,'mbtb'))
