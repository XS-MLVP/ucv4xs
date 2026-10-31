"""A history is not an atomic commit group when its two results service separately."""
import pytest

from suites.frontend.bpu.bpu.case.mixed_visibility import check_mixed_visibility
from suites.frontend.bpu.bpu.coverage.mixed_visibility import MixedVisibilityCoverage
from suites.frontend.bpu.bpu.model.tage.mixed_visibility import PROGRAMS


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
async def test_relearning_uses_independent_branch_versions_after_partial_service(bpu_agent, bpu_sc_output, program):
    coverage = MixedVisibilityCoverage(program)
    try:
        await check_mixed_visibility(bpu_agent, program, coverage)
    finally:
        coverage.write(bpu_sc_output)
