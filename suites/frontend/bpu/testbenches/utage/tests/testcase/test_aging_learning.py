"""Global protection maintenance must not cancel simultaneous real learning."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.aging_learning import check_aging_learning
from suites.frontend.bpu.testbenches.utage.coverage.aging_learning import AgingLearningCoverage
from suites.frontend.bpu.testbenches.utage.model.aging_learning import AgingLearningProgram
from suites.frontend.bpu.testbenches.utage.model.aging_learning import RULES


@pytest.mark.feature('BPU-UTAGE-017')
@pytest.mark.parametrize('table', (0, 1), ids=('short', 'long'))
@pytest.mark.parametrize('rule', RULES)
async def test_maintenance_and_learning_share_old_protection_but_keep_new_direction(utage_agent, table, rule):
    program = AgingLearningProgram(table, rule)
    coverage = AgingLearningCoverage()
    try:
        await check_aging_learning(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
