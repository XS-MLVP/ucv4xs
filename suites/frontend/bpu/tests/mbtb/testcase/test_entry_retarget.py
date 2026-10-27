"""Latest pending target versus ordered write-through, with carry transitions."""
import pytest

from bpuverify.mbtb.coverage.catalog import mbtb_entry_retarget_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_entry_retarget_coverage
from bpuverify.mbtb.model.entry import CARRY_PATTERNS
from bpuverify.mbtb.case.entry_retarget_scenario import check_case
from bpuverify.mbtb.case.resident_scenario import INDEX_CONTEXTS
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-021")
async def test_pending_indirect_retargets_preserve_latest_carry_and_other_residents(mbtb_agent):
    coverage = mbtb_entry_retarget_coverage_model()
    for context in range(len(INDEX_CONTEXTS)):
        for align in range(2):
            for bank in range(2):
                for way in range(2):
                    for mode in ("blocked", "flow"):
                        for pattern in CARRY_PATTERNS:
                            await check_case(mbtb_agent, coverage, context, align, bank, way, mode, pattern)
    coverage.assert_coverage(100.0)
    write_mbtb_entry_retarget_coverage(coverage, REPO_ROOT)
