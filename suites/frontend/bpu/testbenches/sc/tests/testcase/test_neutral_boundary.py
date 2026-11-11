"""Qualified opposite instruction feedback is neutral at both signed edges."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.sc.tests.scenarios.neutral_boundary import check_neutral_boundary
from suites.frontend.bpu.testbenches.sc.coverage.neutral_boundary import NeutralBoundaryCoverage
from suites.frontend.bpu.testbenches.sc.model.neutral_boundary import NeutralBoundaryProgram
from suites.frontend.bpu.testbenches.sc.model.neutral_boundary import PROFILES


@pytest.mark.feature('BPU-SC-005')
@pytest.mark.feature('BPU-SC-014')
@pytest.mark.parametrize('boundary,placement', PROFILES, ids=[a + '.' + b for a, b in PROFILES])
async def test_original_opposite_feedback_is_neutral_at_shared_weight_boundaries(sc_agent, request, boundary, placement):
    program = NeutralBoundaryProgram(boundary, placement)
    coverage = NeutralBoundaryCoverage()
    try:
        await check_neutral_boundary(sc_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'sc'))
        coverage.attach_evidence(request.node.user_properties)
