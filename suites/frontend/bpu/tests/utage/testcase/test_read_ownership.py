"""Ownership intent only; agent drivers launch and monitors associate output."""
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.read_ownership import check_read_ownership
from bpuverify.utage.coverage.read_ownership import ReadOwnershipCoverage
from bpuverify.utage.model.read_ownership import ReadOwnershipProgram


@pytest.mark.feature('BPU-UTAGE-006')
async def test_inflight_query_keeps_original_record_when_other_learning_reuses_retention(utage_agent):
    coverage = ReadOwnershipCoverage()
    try:
        await check_read_ownership(utage_agent, ReadOwnershipProgram(), coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
