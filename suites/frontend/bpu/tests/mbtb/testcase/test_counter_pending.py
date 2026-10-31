"""Read-priority retention versus bank-disjoint flow, across physical geometry."""
from suites.frontend.bpu.models.configuration import *
import pytest

from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_counter_pending_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_counter_pending_coverage
from suites.frontend.bpu.mbtb.case.resident_scenario import INDEX_CONTEXTS
from suites.frontend.bpu.mbtb.case.counter_pending_scenario import check_case
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-020")
async def test_two_counter_updates_survive_live_reads_across_banks_and_ways(mbtb_agent):
    coverage = mbtb_counter_pending_coverage_model()
    for context in range(len(INDEX_CONTEXTS)):
        for align in range(2):
            for bank in range(MAIN_BANKS):
                for way in range(MAIN_WAYS):
                    for taken in range(2):
                        for mode in ("blocked", "flow"):
                            await check_case(mbtb_agent, coverage, context, align, bank, way, taken, mode)
    coverage.assert_coverage(100.0)
    write_mbtb_counter_pending_coverage(coverage, REPO_ROOT)
