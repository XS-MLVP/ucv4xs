"""Source S4 exception/Replay priorities and original effects, not LDU native UT."""
from dataclasses import replace

import pytest

from .ldu_s4_owners import HIT, PATTERNS, S4Program


@pytest.mark.parametrize("pattern",tuple(PATTERNS))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("page",(False,True))
async def test_S4_original_head_tail_exception_writeback_Replay_and_precise_same_slot_recovery(lsq,pattern,lane,page):
    trace=S4Program(lsq,lane,page)
    await trace.dispatch([trace.blocker,trace.target],store=True)
    packet=await trace.split(trace.target,PATTERNS[pattern])
    if packet.execution.need_replay and not packet.update_address:
        await trace.grant(packet)
        retry=tuple(replace(event,mshr_nack=False,miss=False) for event in PATTERNS[pattern])
        packet=await trace.split(trace.target,retry,feedback=True)
        assert not packet.execution.need_replay and packet.update_address
    final=await trace.trap_and_reuse() if packet.exceptions else trace.target
    await trace.finish(final)
    lsq.emit("S4_original_program_complete",pattern=pattern,lane=lane,page=page,
             original_Store_complete=1,completed_Load_UIDs=sum(s["complete"] for s in trace.loads),
             cancelled_Load_UIDs=len(trace.cancelled),source_contract="external_cache_stimuli_frozen_before_S0_not_native_LDU_proof")
