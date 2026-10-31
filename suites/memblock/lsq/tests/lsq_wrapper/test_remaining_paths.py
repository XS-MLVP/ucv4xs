"""Each remaining DA scenario must actually finish original/replacement UIDs."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Data
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load
from .recovery_owners import RecoveryOwners
from .special_owners import SpecialOwners, SpecialStore
from .test_forward_memory import check_bytes
from .test_nuke_memory import expect_rollback, raw_query
from .test_replay_gaps import no_replay
from .test_replay_population import drain_replays
from .uncache_recovery import UncacheRecoveryOwners


async def grant_visible(trace, target_uids):
    for _ in range(150):
        if all("grant" in s for s in trace.loads if s["uid"] in target_uids):
            return
        await trace.cycle(replay_ready=(True,True,True))
    raise AssertionError("all original visible Replay owners were not actually granted")


async def feedback_granted(trace, states):
    packets=[replace(s["load"],execution=replace(s["load"].execution,replay_feedback=True,slot=s["grant"],need_replay=False,causes=0)) for s in states]
    await trace.execute(packets)


@pytest.mark.parametrize("prefix", range(3))
async def test_three_simultaneous_ma_strict_120_slots_all_allocation_alignments_second_sta_wake(lsq,prefix):
    trace=MemoryOwners(lsq)
    for pos in range(prefix):
        load=cached_load(pos,10+pos,0,0x100000+pos*64,0x80100000+pos*64)
        load=replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.BANK_CONFLICT))
        await trace.dispatch(loads=[load])
        await trace.execute([load])
        await trace.replay_complete(load)
        await trace.finish(pending=RobPtr.encode(11+pos))
    old=[StoreOwner(pos,RobPtr.encode(10+prefix),0x20000+pos*16,0xA020000+pos*16,value=0x1234567800000000+pos) for pos in range(8)]
    loads=[]
    for pos in range(prefix,prefix+120):
        load=cached_load(pos,11+pos,8,0x100000+pos*64,0x80100000+pos*64)
        q=replace(load.execution,need_replay=True,causes=1<<Cause.ADDRESS_DEPENDENCE,address_sq=SqPtr.encode(7),data_sq=SqPtr.encode(7),
                  uop=replace(load.execution.uop,strict=True,load_wait=True,store_set_hit=True,wait_sq=SqPtr.encode(7)))
        loads.append(replace(load,execution=q))
    await trace.dispatch(old,loads)
    await trace.execute(loads)
    await no_replay(trace)
    await trace.cycle(addresses=(old[0].address(),Address()),data=(Data(),old[0].data()),
                      address_wakeups=(StoreWakeup(),StoreWakeup(True,SqPtr.encode(0))))
    await no_replay(trace)
    await trace.cycle(addresses=(Address(),old[7].address()),data=(old[7].data(),Data()),
                      address_wakeups=(StoreWakeup(),StoreWakeup(True,SqPtr.encode(7))))
    await trace.write_all()
    selected={s["uid"] for s in trace.loads if s["load"] in loads}
    await drain_replays(trace,selected)
    lsq.prove("LSQ-REPLAY.strict","LSQ-REPLAY.sq_address","LSQ-REPLAY.capacity")


@pytest.mark.parametrize("kept", (1,2,3,5,57,119))
async def test_issued_full_replay_pool_partial_cancel_recycles_only_original_cancelled_slots(lsq,kept):
    await partial_replay_return(lsq,kept)


async def partial_replay_return(lsq,kept,prefix=0):
    trace=RecoveryOwners(lsq)
    if prefix:
        for pos in range(prefix):
            load=cached_load(pos,10+pos,0,0x300000+pos*64,0x90300000+pos*64)
            load=replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.BANK_CONFLICT))
            await trace.dispatch(loads=[load])
            await trace.execute([load])
            await trace.replay_complete(load)
        await trace.finish(pending=RobPtr.encode(10+prefix))
    old=[cached_load(pos,10+pos,0,0x100000+pos*64,0x80100000+pos*64) for pos in range(prefix,prefix+120)]
    old=[replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.TLB_MISS,tlb_id=9)) for load in old]
    await trace.dispatch(loads=old)
    await trace.execute(old)
    await no_replay(trace)
    await trace.cycle(slow_tlb=TlbHint(True,9))
    original=trace.loads[prefix:]
    await grant_visible(trace,{s["uid"] for s in original})
    assert {s["grant"] for s in original}==set(range(120))
    cancelled_slots={s["grant"] for s in original[kept:]}
    assert await trace.cancel(old[kept].execution.uop.rob)==(QueuePtr.encode(prefix+kept),0)
    new=[cached_load(pos,10+pos,0,0x200000+pos*64,0x90200000+pos*64) for pos in range(prefix+kept,prefix+120)]
    new=[replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.BANK_CONFLICT)) for load in new]
    await trace.dispatch(loads=new)
    await trace.execute(new)
    replacement=trace.loads[prefix+120:]
    await grant_visible(trace,{s["uid"] for s in replacement})
    assert {s["grant"] for s in replacement}==cancelled_slots
    await feedback_granted(trace,[s for s in trace.loads if not s["cancelled"] and not s["sent"]])
    await trace.finish(pending=RobPtr.encode(130+prefix))
    lsq.prove("LSQ-RECOVER.partial","LSQ-RECOVER.reuse","LSQ-REPLAY.capacity")


@pytest.mark.parametrize("prefix",(1,2,3))
@pytest.mark.parametrize("kept",(1,2,3,57))
async def test_replay_real_return_tail_alignment_after_completed_prelude_keeps_full_slot_owners(lsq,kept,prefix):
    await partial_replay_return(lsq,kept,prefix)


@pytest.mark.parametrize("kept", (1,2,3))
async def test_partial_real_uncache_cancel_variable_mid_return_alignment_and_original_survivor_data(lsq,kept):
    await partial_uncache_return(lsq,kept)


async def partial_uncache_return(lsq,kept,prefix=0):
    trace=UncacheRecoveryOwners(lsq)
    if prefix:
        prelude=[trace.make_load(pos) for pos in range(prefix)]
        await trace.dispatch(prelude,with_store=True)
        await trace.enqueue(list(range(prefix)))
        for _ in range(prefix):
            await trace.transfer()
        await trace.consume_visible(range(prefix),0)
        await trace.idle(6)
    old=[trace.make_load(pos) for pos in range(prefix,prefix+16)]
    await trace.dispatch(old,with_store=not prefix)
    await trace.enqueue(list(range(prefix,prefix+16)))
    jobs=[await trace.accept() for _ in range(16)]
    assert {a["mid"] for a in jobs}==set(range(16))
    assert await trace.cancel(old[kept].execution.uop.rob)==QueuePtr.encode(prefix+kept)
    for attempt in reversed(jobs):
        await trace.respond(attempt,error=attempt["owner_uid"]>prefix+kept,nderr=attempt["owner_uid"]>prefix+kept)
    await trace.consume_visible(range(prefix,prefix+kept),kept%3)
    await trace.idle(6)
    await trace.discard_cancelled_returns()
    await trace.refill(16-kept,lane=(kept+1)%3)
    await trace.finish()
    lsq.prove("LSQ-RECOVER.partial","LSQ-RECOVER.sent_load","LSQ-RECOVER.reuse","LSQ-BUS.cancelled_return")


@pytest.mark.parametrize("prefix",(1,2,3,9,13))
async def test_uncache_real_return_tail_alignment_after_consumed_original_prelude(lsq,prefix):
    await partial_uncache_return(lsq,3,prefix)


async def test_entry_zero_cancel_in_request_before_elastic_accept_has_no_external_job_and_real_reuse(lsq):
    trace=UncacheRecoveryOwners(lsq)
    old=trace.make_load(0)
    await trace.dispatch([old],with_store=True)
    await trace.cycle(loads=(old,Load(),Load()))
    await trace.idle(2)
    assert not lsq.observed[P.p_uncache_req_valid] and not trace.attempts
    assert await trace.cancel(old.execution.uop.rob)==QueuePtr.encode(0)
    await trace.discard_cancelled_returns()
    assert not trace.attempts
    new=await trace.refill(lane=2)
    assert {a["mid"] for a in new}==set(range(16)) and all(a["response"] and a["consumed"] for a in new)
    await trace.finish()
    lsq.prove("LSQ-RECOVER.reuse")


@pytest.mark.parametrize("sta_lane", range(2))
@pytest.mark.parametrize("group", range(1,7))
async def test_actual_sta_high_raw_select_group_original_rollback_then_same_lq_new_data_finish(lsq,sta_lane,group):
    trace=MemoryOwners(lsq)
    old=[StoreOwner(pos,RobPtr.encode(10+pos//16),0x400000+pos*64,0xB400000+pos*64,value=0x1122334400000000+pos) for pos in range(56)]
    loads=[]
    for pos in range(56):
        load=cached_load(pos,14+pos,56,old[pos].vaddr,old[pos].paddr)
        q=replace(load.execution,need_replay=True,causes=1<<Cause.ADDRESS_DEPENDENCE,address_sq=SqPtr.encode(55),data_sq=SqPtr.encode(55),
                  uop=replace(load.execution.uop,load_wait=True,store_set_hit=True,wait_sq=SqPtr.encode(55)))
        loads.append(replace(load,execution=q))
    await trace.dispatch(old,loads)
    for first in range(0,56,3):
        batch=[raw_query(load) for load in loads[first:first+3]]
        await trace.cycle(raw_queries=tuple(batch)+(RawQuery(),)*(3-len(batch)))
        assert all(lsq.pre_observed[P.io(f"ldu_rawNukeQuery_{lane}_req_ready")] for lane in range(len(batch)))
    await trace.execute(loads)
    await no_replay(trace)
    target=8*group+7
    await trace.write(target,lane=sta_lane)
    await trace.idle(2)
    expect_rollback(lsq,sta_lane,loads[target],old[target].address())
    lsq.expect({P.io(f"nuke_rollback_{1-sta_lane}_valid"):0,P.p_mdpTrain_valid:1,
                P.p_mdpTrain_bits_ftqIdx_value:loads[target].execution.uop.ftq.value,
                P.p_mdpTrain_bits_ftqOffset:loads[target].execution.uop.offset,
                P.p_mdpTrain_bits_stFtqIdx_value:old[target].address().ftq.value,
                P.p_mdpTrain_bits_stFtqOffset:old[target].address().ftq_offset},
               "actual high-group Store STA trains exactly its original younger Load, not a capacity placeholder")
    actual=lsq.observed
    cutoff=RobPtr(bool(actual[P.io(f"nuke_rollback_{sta_lane}_bits_robIdx_flag")]),actual[P.io(f"nuke_rollback_{sta_lane}_bits_robIdx_value")],
                  bool(actual[P.io(f"nuke_rollback_{sta_lane}_bits_robIdx_isFormer")]))
    assert await trace.recover_load_suffix(cutoff)==QueuePtr.encode(target)
    new=[cached_load(pos,70+pos,56,old[pos].vaddr,old[pos].paddr) for pos in range(target,56)]
    await trace.dispatch(loads=new)
    await trace.write_all()
    # All real older Store data/address is stable before the new Load's PA
    # bytes are checked, then S3 is permitted. No query-only fake Load owner.
    for pos,load in enumerate(new):
        await trace.forward(load,pos%3)
        check_bytes(lsq,load,old,pos%3)
    live={s["uid"] for s in trace.loads if not s["cancelled"] and not s["sent"] and s["load"] in loads}
    for _ in range(150):
        if all(s["sent"] for s in trace.loads if s["uid"] in live):
            break
        packets=[]
        for s in trace.loads:
            if s["uid"] in live and "grant" in s and not s["sent"]:
                packets.append(replace(s["load"],execution=replace(s["load"].execution,replay_feedback=True,slot=s["grant"],need_replay=False,causes=0)))
                if len(packets)==3:
                    break
        await trace.cycle(loads=tuple(packets)+(Load(),)*(3-len(packets)),replay_ready=(True,True,True))
    assert all(s["sent"] for s in trace.loads if s["uid"] in live)
    await trace.finish(pending=RobPtr.encode(126))
    lsq.prove("LSQ-RAW.conflict","LSQ-RAW.train","LSQ-RECOVER.partial","LSQ-RECOVER.reuse")


@pytest.mark.parametrize("sta_lane", range(2))
async def test_each_physical_slot_all_cbo_types_original_cache_or_zero_wb_and_full_sq_generations(lsq,sta_lane):
    visits=set()
    for position in range(256):
        cbo=position//64
        store=SpecialStore(position,RobPtr.encode(10+2*position,former=not bool(position&1)),0x400000+position*64,0xB400000+position*64,
                           value=0x8877665500000000+position,cbo=cbo,hyper=bool(position&1))
        trace=SpecialOwners(lsq,[store],start=position,load_position=position,initial_head=store.rob)
        await trace.allocate()
        await trace.write(position,lane=sta_lane)
        wb=await trace.cache_roundtrip(position,hold=position%4)
        assert wb["denied"]==wb["corrupt"]==0 and wb["vaddr"]==store.vaddr and wb["hyper"]==int(store.hyper)
        assert len(trace.cache_requests)==len(trace.cache_responses)==int(cbo!=3)
        assert len(trace.fires)==int(cbo==3)
        await trace.finish()
        visits.add((position%64,cbo))
    assert visits=={(slot,cbo) for slot in range(64) for cbo in range(4)}
    lsq.prove("LSQ-RETIRE.cbo","LSQ-ALLOC.sq_wrap","LSQ-ALLOC.lq_wrap")
