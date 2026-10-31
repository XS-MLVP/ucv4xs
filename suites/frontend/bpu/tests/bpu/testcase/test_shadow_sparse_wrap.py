"""Sparse conditional traffic preserves a survivor before the next update."""
import pytest

from suites.frontend.bpu.bpu.case.bypass.sparse_wrap import check_sparse_wrap


@pytest.mark.feature('BPU-INT-064')
async def test_sparse_wrap_returns_retained_old_shadow_payload(bpu_agent, bpu_sc_output):
    await check_sparse_wrap(bpu_agent, bpu_sc_output)
