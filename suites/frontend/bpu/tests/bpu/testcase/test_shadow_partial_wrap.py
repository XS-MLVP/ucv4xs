"""Functional intent; state preparation, protocol and checking are reusable."""
import pytest

from suites.frontend.bpu.bpu.case.bypass.partial_wrap import check_partial_wrap


@pytest.mark.feature('BPU-INT-063')
async def test_partial_wrap_returns_retained_old_shadow_payload(bpu_agent, bpu_sc_output):
    await check_partial_wrap(bpu_agent, bpu_sc_output)
