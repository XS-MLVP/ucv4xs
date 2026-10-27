"""Maximum-width index learning, and resolved instruction-type eligibility."""
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.semantic import boundary_lifecycle, nonconditional_feedback
from bpuverify.utage.coverage.semantic import SemanticCoverage


@pytest.mark.feature('BPU-UTAGE-024')
async def test_maximum_a0_index_independent_a1_tag_lifecycle(utage_agent):
    coverage = SemanticCoverage('boundary')
    try:
        await boundary_lifecycle(utage_agent, coverage)
        for group in coverage.groups.values():
            group.assert_coverage(100)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))


@pytest.mark.feature('BPU-UTAGE-025')
@pytest.mark.parametrize('kind', (2, 3), ids=('direct', 'indirect'))
async def test_resolved_nonconditional_same_position_preserves_warm_conditional(utage_agent, kind):
    coverage = SemanticCoverage('resolved-type')
    try:
        await nonconditional_feedback(utage_agent, coverage, kind=kind)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
