"""066: independent original source beats the opposite base before any repair."""
import pytest
from bpuverify.bpu.case.early_opposition import check_early_opposition
from bpuverify.bpu.coverage.early_opposition import EarlyOppositionCoverage


@pytest.mark.feature('BPU-INT-066')
async def test_owned_negative_provider_overrules_positive_ahead_and_gains_useful(bpu_agent,bpu_sc_output):
    coverage=EarlyOppositionCoverage()
    try:await check_early_opposition(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
