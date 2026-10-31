"""Semantic query history; all phase, source and monitor machinery is below cases."""
import json
import pytest
from suites.frontend.bpu.bpu.case.common_query import run
from suites.frontend.bpu.bpu.coverage.common_query import CommonQueryCoverage
from suites.frontend.bpu.bpu.model.common_query import PROFILES


@pytest.mark.feature('BPU-INT-043')
@pytest.mark.feature('BPU-INT-094')
@pytest.mark.feature('BPU-INT-099')
@pytest.mark.parametrize('profile', PROFILES)
async def test_every_original_query_owns_its_read_and_feedback_history(bpu_agent, bpu_sc_output, request, profile):
    coverage = CommonQueryCoverage(profile)
    try:
        facts = await run(bpu_agent, profile, coverage)
        request.node.user_properties.append(('semantic_bpu_common_query_history', json.dumps(facts, sort_keys=True)))
    finally:
        coverage.write(bpu_sc_output)
