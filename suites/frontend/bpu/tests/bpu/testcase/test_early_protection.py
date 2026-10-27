"""Original provider remains usable at protection limits and after reversal."""
import pytest

from bpuverify.bpu.case.early_protection import check_early_protection
from bpuverify.bpu.coverage.early_protection import EarlyProtectionCoverage
from bpuverify.bpu.model.early_protection import EDGES


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_original_provider_protection_limits_and_reverse_recovery(bpu_agent, bpu_sc_output, mode):
    coverage = EarlyProtectionCoverage()
    try:
        await check_early_protection(bpu_agent, mode, coverage)
    finally:
        coverage.write(bpu_sc_output)
