import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.tage.case.semantic import history_ownership
from bpuverify.tage.coverage.semantic import SemanticCoverage


@pytest.mark.feature('BPU-TAGE-036')
async def test_history_specific_learning_and_pipeline_restore(tage_agent):
    coverage = SemanticCoverage()
    try:
        await history_ownership(tage_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'tage'))
