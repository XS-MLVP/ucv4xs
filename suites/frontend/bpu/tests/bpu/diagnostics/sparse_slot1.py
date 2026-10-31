"""Explicit candidate only, not default collection or functional PASS credit."""
from suites.frontend.bpu.bpu.case.bypass.sparse_wrap import check_sparse_wrap


async def test_sparse_slot1_candidate(bpu_agent, bpu_sc_output):
    await check_sparse_wrap(bpu_agent, bpu_sc_output, survivor_slot=1)
