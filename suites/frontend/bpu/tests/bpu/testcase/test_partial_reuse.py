"""A partially serviced set admits a fresh identity without dropping others."""
import pytest
from bpuverify.bpu.case.partial_reuse import check_partial_reuse
from bpuverify.bpu.coverage.partial_reuse import PartialReuseCoverage


@pytest.mark.feature('BPU-INT-089')
async def test_new_learning_reuses_partially_serviced_capacity_without_losing_pending_identities(bpu_agent, bpu_sc_output):
    coverage = PartialReuseCoverage()
    try:
        await check_partial_reuse(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
