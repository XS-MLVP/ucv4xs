"""Autonomous integrated failure/maintenance proof, not a bank sweep."""
import pytest

from bpuverify.bpu.case.early_aging import check_early_aging
from bpuverify.bpu.coverage.early_aging import EarlyAgingCoverage


@pytest.mark.feature('BPU-INT-051')
@pytest.mark.estimated_runtime(90)
async def test_owned_guidance_counts_real_failures_and_ages_without_learning_from_cancelled_younger_path(
        bpu_agent, bpu_sc_output):
    coverage = EarlyAgingCoverage()
    try:
        await check_early_aging(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
