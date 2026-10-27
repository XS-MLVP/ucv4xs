"""No edge, tasks, gather, observed golden seed or physical-coordinate sweep."""
import pytest
from bpuverify.bpu.case.main_rewrite import check_main_rewrite
from bpuverify.bpu.coverage.main_rewrite import MainRewriteCoverage


@pytest.mark.feature('BPU-INT-095')
async def test_same_original_main_record_supersedes_pending_complete_versions_and_reactivates_after_service(bpu_agent,bpu_sc_output):
    coverage=MainRewriteCoverage()
    try:await check_main_rewrite(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
