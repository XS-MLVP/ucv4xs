"""Logical lifetimes; drivers and monitors own every pipeline boundary."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.working_set import check_working_set
from suites.frontend.bpu.utage.coverage.working_set import WorkingSetCoverage
from suites.frontend.bpu.utage.model.working_set import MODES, SIZES, WorkingSetProgram


@pytest.mark.feature('BPU-UTAGE-020')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('mode', MODES)
async def test_history_working_set_retains_independent_learning_after_turnover(utage_agent, size, mode, request):
    program = WorkingSetProgram(size, mode)
    coverage = WorkingSetCoverage(program)
    try:
        await check_working_set(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        coverage.attach_evidence(request.node.user_properties)
