"""Ordinary LD source boundary PF/AF, original effects and precise recovery."""
from dataclasses import replace

import pytest

from .ldu_s4_plain_owners import PATTERNS, OrdinaryS4Program


@pytest.mark.parametrize("pattern",tuple(PATTERNS))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("page",(False,True))
async def test_ordinary_LD_S4_PF_AF_priorities_real_Replay_and_same_slot_recovery(lsq,pattern,lane,page):
    trace=OrdinaryS4Program(lsq,lane,page)
    await trace.dispatch([trace.blocker,trace.target],store=True)
    packet=await trace.split(trace.target,PATTERNS[pattern])
    if packet.execution.need_replay and not packet.update_address:
        await trace.grant(packet)
        packet=await trace.split(trace.target,tuple(replace(e,mshr_nack=False,miss=False) for e in PATTERNS[pattern]),feedback=True)
        assert not packet.execution.need_replay and packet.update_address
    final=await trace.trap_and_reuse() if packet.exceptions else trace.target
    await trace.finish(final)
