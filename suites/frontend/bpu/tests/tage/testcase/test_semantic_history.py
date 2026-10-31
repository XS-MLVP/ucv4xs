import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.semantic import history_ownership
from suites.frontend.bpu.tage.coverage.semantic import SemanticCoverage


@pytest.mark.feature('BPU-TAGE-036')
async def test_history_specific_learning_and_pipeline_restore(tage_agent):
    coverage = SemanticCoverage()
    try:
        await history_ownership(tage_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'tage'))
