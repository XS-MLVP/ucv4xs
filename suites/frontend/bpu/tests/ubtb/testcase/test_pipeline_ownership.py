"""Different branch identities, including misses, overlap in one real DUT."""
import json

import pytest

from bpuverify.common.coverage.pipeline_ownership import PipelineOwnershipCoverage, PROFILES
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.ubtb.case.pipeline_ownership import check_pipeline_ownership


@pytest.mark.feature('BPU-UBTB-007')
@pytest.mark.feature('BPU-UBTB-013')
@pytest.mark.parametrize('profile', PROFILES['ubtb'])
async def test_distinct_originals_and_misses_keep_their_own_responses(ubtb_agent, request, profile):
    coverage = PipelineOwnershipCoverage('ubtb', profile)
    try:
        await check_pipeline_ownership(ubtb_agent, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'ubtb'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('semantic_pipeline_ownership', json.dumps(coverage.evidence, sort_keys=True)))
