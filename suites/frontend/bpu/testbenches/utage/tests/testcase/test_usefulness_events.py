"""Readable protection obligations; environment owns scheduling and observation."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.usefulness_events import check_usefulness_event
from suites.frontend.bpu.testbenches.utage.coverage.usefulness_events import UsefulnessCoverage
from suites.frontend.bpu.testbenches.utage.model.usefulness_events import MODES
from suites.frontend.bpu.testbenches.utage.model.usefulness_events import RULES
from suites.frontend.bpu.testbenches.utage.model.usefulness_events import UsefulnessProgram


@pytest.mark.feature('BPU-UTAGE-020')
@pytest.mark.parametrize('table', (0, 1), ids=('short', 'long'))
async def test_new_identity_receives_initial_protection_without_changing_neighbor(utage_agent, table):
    program = UsefulnessProgram(table, 'initial-protection')
    coverage = UsefulnessCoverage(program)
    try:
        await check_usefulness_event(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('table', (0, 1), ids=('short', 'long'))
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('rule', RULES)
async def test_qualified_feedback_protection_saturation_recovery_and_base_agreement(utage_agent, table, mode, rule):
    program = UsefulnessProgram(table, rule, mode)
    coverage = UsefulnessCoverage(program)
    try:
        await check_usefulness_event(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
