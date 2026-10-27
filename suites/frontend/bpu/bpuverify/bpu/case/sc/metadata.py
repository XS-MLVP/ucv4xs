"""bpuverify.bpu.case.sc.metadata components."""

from __future__ import annotations
from bpuverify.bpu.transaction.types import BpuRedirect


async def revisit_from_redirect(agent, pc: int, redirect_meta):
    boundary = await agent.redirect(BpuRedirect(pc, redirect_meta))
    return await agent.next_transaction(start_pc=pc, after_tick=boundary)
