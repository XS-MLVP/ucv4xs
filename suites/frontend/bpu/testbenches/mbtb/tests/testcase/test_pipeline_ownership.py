"""Different fetch windows, including misses, overlap in one real DUT."""
import json

import pytest

from suites.frontend.bpu.testbenches.shared.coverage.pipeline_ownership import PipelineOwnershipCoverage
from suites.frontend.bpu.testbenches.mbtb.coverage.pipeline_ownership import PROFILES
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.pipeline_ownership import check_pipeline_ownership


@pytest.mark.feature('BPU-MBTB-007')
@pytest.mark.parametrize('profile', PROFILES)
async def test_distinct_originals_and_misses_keep_their_own_responses(mbtb_agent, request, profile):
    coverage = PipelineOwnershipCoverage('mbtb', profile, profiles={'mbtb': PROFILES})
    try:
        await check_pipeline_ownership(mbtb_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('semantic_pipeline_ownership', json.dumps(coverage.evidence, sort_keys=True)))
