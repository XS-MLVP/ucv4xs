"""Mixed valid feedback and later absence consumers, no physical matrix."""
import pytest

from suites.frontend.bpu.bpu.case.tage.interleaved import check_interleaved_learning
from suites.frontend.bpu.bpu.coverage.tage.interleaved import InterleavedCoverage


@pytest.mark.feature('BPU-INT-084')
async def test_interleaved_untracked_conditionals_do_not_shift_or_acquire_owned_tage_learning(bpu_agent,bpu_sc_output):
    coverage = InterleavedCoverage()
    try:await check_interleaved_learning(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
