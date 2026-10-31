"""No signal edges or task scheduling in the scenario entry point."""
import pytest

from suites.frontend.bpu.bpu.case.micro_forwarding import check_micro_forwarding
from suites.frontend.bpu.bpu.coverage.micro_forwarding import MicroForwardingCoverage


@pytest.mark.feature('BPU-INT-083')
async def test_adjacent_same_key_positive_updates_survive_public_depletion_proof(bpu_agent,bpu_sc_output):
    coverage = MicroForwardingCoverage()
    try:
        await check_micro_forwarding(bpu_agent,coverage)
    finally:
        coverage.write(bpu_sc_output)
