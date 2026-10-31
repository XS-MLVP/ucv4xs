"""Original PC/history ownership must survive unrelated adjacent requests."""
import json

import pytest

from suites.frontend.bpu.coverage.pipeline_ownership import PipelineOwnershipCoverage, PROFILES
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ittage.case.pipeline_ownership import check_pipeline_ownership


@pytest.mark.feature('BPU-ITTAGE-006')
@pytest.mark.feature('BPU-ITTAGE-009')
@pytest.mark.parametrize('profile', PROFILES['ittage'])
async def test_distinct_originals_and_misses_keep_their_own_responses(ittage_agent, request, profile):
    coverage = PipelineOwnershipCoverage('ittage', profile)
    try:
        await check_pipeline_ownership(ittage_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'ittage'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('semantic_pipeline_ownership', json.dumps(coverage.evidence, sort_keys=True)))
