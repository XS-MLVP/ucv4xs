import pytest

from bpuverify.bpu.case.tage.learning import check_sparse_learning
from bpuverify.bpu.coverage.tage.learning import LearningCoverage
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-075')
async def test_sparse_two_conditional_feedback_preserves_each_owned_learning_update(bpu_agent):
    coverage = LearningCoverage()
    try:
        await check_sparse_learning(bpu_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
