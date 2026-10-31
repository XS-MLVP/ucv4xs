"""Integrated capacity is one functional boundary, not a bank/set sweep."""
import pytest

from suites.frontend.bpu.bpu.case.micro_capacity import check_micro_capacity
from suites.frontend.bpu.bpu.coverage.micro_capacity import MicroCapacityCoverage


@pytest.mark.feature('BPU-INT-082')
async def test_owned_micro_capacity_eviction_keeps_recent_prediction_and_other_entries(bpu_agent,bpu_sc_output):
    coverage = MicroCapacityCoverage()
    try:
        await check_micro_capacity(bpu_agent,coverage)
    finally:
        coverage.write(bpu_sc_output)
