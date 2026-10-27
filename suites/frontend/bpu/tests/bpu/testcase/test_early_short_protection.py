"""Short-provider boundaries cannot be inferred from a passing long provider."""
import pytest

from bpuverify.bpu.case.early_short_protection import check_early_short_protection
from bpuverify.bpu.coverage.early_short_protection import EarlyShortProtectionCoverage
from bpuverify.bpu.model.early_short_protection import EDGES


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_original_short_provider_limits_and_reverse_recovery(bpu_agent, bpu_sc_output, mode):
    coverage = EarlyShortProtectionCoverage()
    try:
        await check_early_short_protection(bpu_agent, mode, coverage)
    finally:
        coverage.write(bpu_sc_output)
