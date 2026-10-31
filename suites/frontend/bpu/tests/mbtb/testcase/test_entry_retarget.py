"""Latest pending target versus ordered write-through, with carry transitions."""
from suites.frontend.bpu.models.configuration import *
import pytest

from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_entry_retarget_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_entry_retarget_coverage
from suites.frontend.bpu.mbtb.model.entry import CARRY_PATTERNS
from suites.frontend.bpu.mbtb.case.entry_retarget_scenario import check_case
from suites.frontend.bpu.mbtb.case.resident_scenario import INDEX_CONTEXTS
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-021")
async def test_pending_indirect_retargets_preserve_latest_carry_and_other_residents(mbtb_agent):
    coverage = mbtb_entry_retarget_coverage_model()
    for context in range(len(INDEX_CONTEXTS)):
        for align in range(2):
            for bank in range(MAIN_BANKS):
                for way in range(MAIN_WAYS):
                    for mode in ("blocked", "flow"):
                        for pattern in CARRY_PATTERNS:
                            await check_case(mbtb_agent, coverage, context, align, bank, way, mode, pattern)
    coverage.assert_coverage(100.0)
    write_mbtb_entry_retarget_coverage(coverage, REPO_ROOT)
