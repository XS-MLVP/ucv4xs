"""One semantic lifetime; no speculative-slot or address matrix."""
import pytest
from suites.frontend.bpu.bpu.case.ras.capacity import check_ras_reuse
from suites.frontend.bpu.bpu.coverage.ras_reuse import RasReuseCoverage


@pytest.mark.feature('BPU-INT-096')
async def test_guarded_ras_rollback_reclaims_cancelled_versions_and_reuses_storage_for_a_new_call_identity(bpu_agent,bpu_sc_output):
    coverage=RasReuseCoverage()
    try:await check_ras_reuse(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
