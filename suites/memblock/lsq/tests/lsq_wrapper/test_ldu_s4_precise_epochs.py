"""Real S4 generations and an outstanding head Cache job before tail fault."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from .ldu_s4_epoch_owners import EpochPreciseS4Program, EPOCH_CASES, MISS_FAULT_CASES, PATTERNS
from .memory_owners import cached_load
from .mixed_owners import rob_pointer

from suites.memblock.lsq.legacy_pins import P


@pytest.mark.parametrize("page,pattern",MISS_FAULT_CASES)
@pytest.mark.parametrize("lane",range(3))
async def test_S4_real_head_miss_returns_before_persistent_tail_fault_and_head_trap(lsq,page,pattern,lane):
    trace=EpochPreciseS4Program(lsq,lane,page,page_tag=1)
    try:await trace.run_program(PATTERNS[pattern])
    except BaseException as exc:
        trace.write_report(case=dict(page=page,pattern=pattern,lane=lane),passed=False,error=repr(exc));raise
    trace.write_report(case=dict(page=page,pattern=pattern,lane=lane),passed=True)


@pytest.mark.parametrize("rotation",range(3))
async def test_S4_precise_360_programs_actual_all_LQ_SQ_codes_and_UID_generations(lsq,rotation):
    sq=lq=uid=0;order=8
    programs=[];targets=set();stores=set();result=None
    try:
        for index in range(360):
            page,pattern=EPOCH_CASES[index%len(EPOCH_CASES)]
            trace=EpochPreciseS4Program(lsq,(index+rotation)%3,page,start_sq=sq,start_lq=lq,start_rob=order,uid_base=uid,page_tag=index+1)
            result=await trace.run_program(PATTERNS[pattern])
            target=next(s for s in result["UID_terminal_states"] if s["uid"]==uid+3)
            assert target["queue_absolute_position"]==lq+1
            targets.add(target["queue_absolute_position"]%240)
            stores.add(next(s for s in result["UID_terminal_states"] if s["kind"]=="store")["queue_absolute_position"]%256)
            sq,lq,order,uid=sq+1,lq+3,order+10,trace.sequence
            if index in(119,239):
                filler=cached_load(lq,rob_pointer(order),sq,0x79000+4096*index,0xA379000+4096*index)
                await trace.dispatch([filler]);await trace.clean_aligned(filler)
                trace.base=replace(trace.base,pending=rob_pointer(order+1),pending_next=rob_pointer(order+1))
                for _ in range(20):await trace.cycle()
                assert all(s["complete"] or s["cancelled"] for s in trace.loads)
                assert lsq.observed[P.p_lqEmpty] and lsq.observed[P.p_sqEmpty]
                result=trace.checker.finish()
                result.update(native_prefix_records=trace.boot_records,native_prefix_last_tick=trace.boot_tick,native_records_at_end=lsq.journal.records)
                lq,order,uid=lq+1,order+1,trace.sequence
            assert result["queue_tails"]==dict(SQ=sq,LQ=lq)
            assert trace.checker.sh==sq and trace.checker.lh==lq
            programs.append(dict(index=index,pattern=pattern,page=page,lane=trace.lane,summary=result))
        assert (sq,lq,order)==(360,1082,3610) and targets==set(range(240)) and stores==set(range(256))
    except BaseException as exc:
        with Path(lsq.journal.name).with_name("s4-precise-epochs-summary.json").open("x") as out:
            out.write(json.dumps(dict(nodeid=lsq.nodeid,passed=False,error=repr(exc),rotation=rotation,completed_programs=programs,last_partial_counts=dict(trace.checker.counts)),indent=2)+"\n")
        raise
    with Path(lsq.journal.name).with_name("s4-precise-epochs-summary.json").open("x") as out:
        out.write(json.dumps(dict(nodeid=lsq.nodeid,passed=True,rotation=rotation,programs=programs,distinct_target_LQ_codes=len(targets),
                                 distinct_Store_SQ_codes=len(stores),SQ_tail=sq,LQ_tail=lq,ROB_absolute=order,allocated_UIDs=uid,
                                 scope="terminal UID/source/effect witnesses only; no per-cycle JSON or waveforms"),indent=2)+"\n")
