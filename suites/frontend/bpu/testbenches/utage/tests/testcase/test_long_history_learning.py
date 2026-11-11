"""Communication modes are semantic parameters, not physical bank coordinates."""
import pytest
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.long_history_learning import check_long_history_learning
from suites.frontend.bpu.testbenches.utage.coverage.long_history_learning import LongHistoryLearningCoverage
from suites.frontend.bpu.testbenches.utage.model.long_history_learning import MODES


@pytest.mark.feature('BPU-UTAGE-018')
@pytest.mark.parametrize('mode',MODES)
async def test_opposed_long_history_paths_keep_independent_learning_from_real_overlapping_sources(utage_agent,mode):
    coverage = LongHistoryLearningCoverage(mode)
    try:
        await check_long_history_learning(utage_agent,mode,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'utage'))
