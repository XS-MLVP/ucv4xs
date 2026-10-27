"""Tighter semantic wrap boundaries, not a physical bank/set sweep."""
import pytest

from bpuverify.bpu.case.bypass.sparse_wrap import check_sparse_wrap


@pytest.mark.feature('BPU-INT-065')
@pytest.mark.parametrize('survivor_slot', (5, 4, 3), ids=('upper5', 'upper4', 'upper3'))
async def test_sparse_wrap_returns_old_payload_at_tighter_boundary(bpu_agent, bpu_sc_output, survivor_slot):
    await check_sparse_wrap(bpu_agent, bpu_sc_output, survivor_slot=survivor_slot)
