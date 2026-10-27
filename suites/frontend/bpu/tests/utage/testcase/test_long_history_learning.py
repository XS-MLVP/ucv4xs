"""Communication modes are semantic parameters, not physical bank coordinates."""
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.long_history_learning import check_long_history_learning
from bpuverify.utage.coverage.long_history_learning import LongHistoryLearningCoverage
from bpuverify.utage.model.long_history_learning import MODES


@pytest.mark.feature('BPU-UTAGE-018')
@pytest.mark.parametrize('mode',MODES)
async def test_opposed_long_history_paths_keep_independent_learning_from_real_overlapping_sources(utage_agent,mode):
    coverage = LongHistoryLearningCoverage(mode)
    try:
        await check_long_history_learning(utage_agent,mode,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'utage'))
