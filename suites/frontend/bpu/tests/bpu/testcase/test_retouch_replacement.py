"""A real retained hit changes the access contract of the following full miss."""
import pytest
from suites.frontend.bpu.bpu.case.retouch_replacement import check_retouch_replacement
from suites.frontend.bpu.bpu.coverage.retouch_replacement import RetouchReplacementCoverage
from suites.frontend.bpu.bpu.model.tage.retouch_replacement import PROGRAMS


@pytest.mark.feature('BPU-INT-088')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_full_learning_retouch_controls_next_replacement_and_all_survivors(bpu_agent,bpu_sc_output,program):
    coverage=RetouchReplacementCoverage(program)
    try:await check_retouch_replacement(bpu_agent,coverage,program)
    finally:coverage.write(bpu_sc_output)
