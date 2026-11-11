"""Ownership intent only; agent drivers launch and monitors associate output."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.read_ownership import check_read_ownership
from suites.frontend.bpu.testbenches.utage.coverage.read_ownership import ReadOwnershipCoverage
from suites.frontend.bpu.testbenches.utage.model.read_ownership import ReadOwnershipProgram


@pytest.mark.feature('BPU-UTAGE-006')
async def test_inflight_query_keeps_original_record_when_other_learning_reuses_retention(utage_agent):
    coverage = ReadOwnershipCoverage()
    try:
        await check_read_ownership(utage_agent, ReadOwnershipProgram(), coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
