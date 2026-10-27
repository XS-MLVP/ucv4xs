"""Captured-cold requests must not move a retained key to another shadow way."""
import pytest

from bpuverify.mbtb.coverage.catalog import mbtb_shadow_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_shadow_coverage
from bpuverify.mbtb.model.entry import CARRY_PATTERNS
from bpuverify.mbtb.model.shadow import SHADOW_PHASES
from bpuverify.mbtb.case.resident_scenario import INDEX_CONTEXTS
from bpuverify.mbtb.case.shadow_scenario import check_case
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-023")
async def test_captured_cold_rewrites_keep_original_shadow_owner_during_replacement(mbtb_agent):
    coverage = mbtb_shadow_coverage_model()
    for context in range(len(INDEX_CONTEXTS)):
        for align in range(2):
            for bank in range(2):
                for owner in range(2):
                    for phase in SHADOW_PHASES:
                        for mode in ("blocked", "flow"):
                            for pattern in CARRY_PATTERNS:
                                await check_case(mbtb_agent, coverage, context, align, bank, owner, phase, mode, pattern)
    coverage.assert_coverage(100.0)
    write_mbtb_shadow_coverage(coverage, REPO_ROOT)
