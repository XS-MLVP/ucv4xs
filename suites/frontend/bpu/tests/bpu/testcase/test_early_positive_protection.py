"""T provider protection needs its own actual-boundary and consumer proof."""
import pytest

from bpuverify.bpu.case.early_positive_protection import check_early_positive_protection
from bpuverify.bpu.coverage.early_positive_protection import EarlyPositiveProtectionCoverage
from bpuverify.bpu.model.early_positive_protection import EDGES


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_taken_original_protection_limits_and_recovery(bpu_agent, bpu_sc_output, mode):
    coverage = EarlyPositiveProtectionCoverage()
    try:
        await check_early_positive_protection(bpu_agent, mode, coverage)
    finally:
        coverage.write(bpu_sc_output)
