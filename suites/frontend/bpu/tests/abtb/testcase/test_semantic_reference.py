"""A destination is a branch record, not merely a shared partial tag."""
import pytest

from suites.frontend.bpu.abtb.case.semantic import pending_corrections, serial_corrections
from suites.frontend.bpu.abtb.coverage.semantic import SemanticCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-ABTB-053')
@pytest.mark.parametrize('distinct', (False, True), ids=('same-destination', 'distinct-destinations'))
async def test_pending_target_corrections_preserve_destination_ownership(abtb_agent, distinct):
    coverage = SemanticCoverage()
    try:
        await pending_corrections(abtb_agent, coverage, distinct=distinct)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'abtb'))


@pytest.mark.feature('BPU-ABTB-053')
async def test_serial_distinct_target_corrections_are_a_nonoverlap_control(abtb_agent):
    await serial_corrections(abtb_agent)
