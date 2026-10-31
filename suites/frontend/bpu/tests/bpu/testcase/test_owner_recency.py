"""One original feedback need not touch every branch in its prediction."""
import pytest

from suites.frontend.bpu.bpu.case.retouch_replacement import check_retouch_replacement
from suites.frontend.bpu.bpu.coverage.owner_recency import OwnerRecencyCoverage
from suites.frontend.bpu.bpu.model.tage.owner_recency import PROGRAMS


@pytest.mark.feature('BPU-INT-088')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_subset_feedback_preserves_independent_recency_and_complete_results(bpu_agent,bpu_sc_output,program):
    coverage=OwnerRecencyCoverage(program)
    try:await check_retouch_replacement(bpu_agent,coverage,program)
    finally:coverage.write(bpu_sc_output)
