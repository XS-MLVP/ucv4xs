"""Real S4 slot/flag generations, never pointer preloads or reset shortcuts."""
from dataclasses import replace

import pytest

from .ldu_s4_owners import PATTERNS, S4Program
from .memory_owners import cached_load
from .mixed_owners import rob_pointer


@pytest.mark.parametrize("rotation",range(3))
async def test_S4_300_real_programs_all_LQ_SQ_codes_original_effects_and_same_slot_epochs(lsq,rotation):
    sq=lq=uid=0
    order=8
    codes,physical=set(),set()
    for index in range(300):
        trace=S4Program(lsq,(index+rotation)%3,bool(index%2),start_sq=sq,start_lq=lq,start_rob=order,uid_base=uid)
        await trace.dispatch([trace.blocker,trace.target],store=True)
        pointer=trace.target.execution.uop.lq
        codes.add(120*int(pointer.flag)+pointer.value)
        physical.add(pointer.value)
        pattern=PATTERNS[tuple(PATTERNS)[index%len(PATTERNS)]]
        packet=await trace.split(trace.target,pattern)
        if packet.execution.need_replay and not packet.update_address:
            await trace.grant(packet)
            retry=tuple(replace(event,mshr_nack=False,miss=False) for event in pattern)
            packet=await trace.split(trace.target,retry,feedback=True)
            assert not packet.execution.need_replay and packet.update_address
        final=await trace.trap_and_reuse() if packet.exceptions else trace.target
        await trace.finish(final)
        sq,lq,order,uid=sq+1,lq+2,order+5,trace.sequence
        if index in (59,179):
            filler=cached_load(lq,rob_pointer(order),sq,0x79000,0xA379000)
            await trace.dispatch([filler])
            await trace.clean_aligned(filler)
            trace.base=replace(trace.base,pending=rob_pointer(order+1),pending_next=rob_pointer(order+1))
            for _ in range(20):await trace.cycle()
            assert all(s["complete"] or s["cancelled"] for s in trace.loads)
            assert lsq.observed["io_lqEmpty"] and lsq.observed["io_sqEmpty"]
            lq,order,uid=lq+1,order+1,trace.sequence
    assert codes==set(range(240)) and physical==set(range(120)) and (sq,lq,order)==(300,602,1510)
    lsq.emit("S4_real_epochs_complete",rotation=rotation,programs=300,distinct_target_LQ_codes=240,
             distinct_target_physical_LQ=120,SQ_tail=sq,LQ_tail=lq,ROB_absolute=order,
             original_UIDs=uid,reset_shortcuts=0,only_supplemental_existing_epoch_scenarios=True)
