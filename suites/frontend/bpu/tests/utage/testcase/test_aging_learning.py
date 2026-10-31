"""Global protection maintenance must not cancel simultaneous real learning."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.aging_learning import check_aging_learning
from suites.frontend.bpu.utage.coverage.aging_learning import AgingLearningCoverage
from suites.frontend.bpu.utage.model.aging_learning import AgingLearningProgram, RULES


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
