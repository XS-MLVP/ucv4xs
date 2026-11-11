"""Logical lifetimes; drivers and monitors own every pipeline boundary."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.working_set import check_working_set
from suites.frontend.bpu.testbenches.utage.coverage.working_set import WorkingSetCoverage
from suites.frontend.bpu.testbenches.utage.model.working_set import MODES
from suites.frontend.bpu.testbenches.utage.model.working_set import SIZES
from suites.frontend.bpu.testbenches.utage.model.working_set import WorkingSetProgram


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
