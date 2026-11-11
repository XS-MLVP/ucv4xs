"""Real128 Store flows,56 RAW records,57th Load native capacity feedback."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs, replays_absent
from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners, StoreOwner, cached_load
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.mixed_owners import rob_pointer


@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("wake",("pool_credit","address_prefix"))
async def test_real128_stores_RAW_full57th_Load_original_slot_all_effects(sq_lsq,lane,wake):
    lsq=sq_lsq
    trace=MemoryOwners(lsq)
    start=16
    trace.base=replace(trace.base,pending=rob_pointer(start),pending_next=rob_pointer(start))
    stores=[StoreOwner(pos,rob_pointer(start+pos+int(wake=="pool_credit" and pos==127)),
                       0x500000+64*pos,0xA500000+64*pos,value=0x8877665500000000+pos) for pos in range(128)]
    loads=[]
    for pos in range(57):
        boundary=127 if wake=="pool_credit" and pos==0 else 128
        order=start+127 if wake=="pool_credit" and pos==0 else start+128+pos
        loads.append(cached_load(pos,rob_pointer(order),boundary,0x600000+64*pos,0xA600000+64*pos))
    if wake=="pool_credit":
        await trace.dispatch(stores[:127],[loads[0]])
        await trace.dispatch(stores[127:],loads[1:])
    else:await trace.dispatch(stores,loads)

    async def issue(load,*,feedback=False):
        u=load.execution.uop
        qs,ts,rs,ws,packets=[Query()]*3,[Translation()]*3,[RarQuery()]*3,[RawQuery()]*3,[Load()]*3
        qs[lane]=Query(True,load.execution.vaddr,u.sq,3)
        await trace.cycle(queries=tuple(qs))
        ts[lane]=Translation(load.paddr)
        await trace.cycle(translations=tuple(ts))
        rs[lane]=RarQuery(True,u.rob,u.lq,load.paddr,True,False)
        ws[lane]=RawQuery(True,u.rob,u.sq,load.paddr,load.execution.mask,True,u.rvc,u.ftq,u.offset,u.checkpoint)
        await trace.cycle(rar_queries=tuple(rs),raw_queries=tuple(ws))
        ready=lsq.pre_response.raw_nuke[lane].req_ready
        assert lsq.pre_response.rar_nuke[lane].req_ready and not lsq.response.rar_nuke[lane].nuke
        assert ready==int(feedback or load is not loads[-1])
        cause=0 if ready else 1<<Cause.RAW_CAPACITY
        q=replace(load.execution,need_replay=bool(cause),causes=cause,replay_feedback=feedback,aligned_type=3,
                  last_beat=bool(load.paddr&64),
                  slot=trace.active_loads[u.lq]["grant"] if feedback else 0)
        packets[lane]=replace(load,execution=q,update_address=not bool(cause))
        revoke=tuple(bool(cause) and b==lane for b in range(3))
        await trace.cycle(loads=tuple(packets),rar_revoke_last=revoke,raw_revoke_last=revoke)
        return packets[lane]

    for load in loads[:-1]:await issue(load)
    blocked=await issue(loads[-1])
    assert blocked.execution.causes==1<<Cause.RAW_CAPACITY
    for _ in range(8):
        await trace.cycle()
        lsq.expect(obs(replays=replays_absent()),"full RAW and128 unready old Store addresses retain original capacity wait")
    await trace.write_all(range(64))
    trace.base=replace(trace.base,pending=stores[64].rob,pending_next=stores[64].rob,sbuffer_ready=(True,True))
    for _ in range(180):
        await trace.cycle()
        if trace.sq_head==64:break
    assert trace.sq_head==64
    trace.base=replace(trace.base,sbuffer_ready=(False,False))
    await trace.write_all(range(64,127))
    for _ in range(80):
        await trace.cycle()
        if any(item.valid for item in lsq.response.replays):break
    valid=any(item.valid for item in lsq.response.replays)
    assert valid==(wake=="pool_credit"),"actual credit may wake with last Store address still unknown; full tail128 must wait"
    if wake=="address_prefix":await trace.write_all((127,))
    for _ in range(80):
        if any(item.valid for item in lsq.response.replays):break
        await trace.cycle()
    bank=next(b for b,item in enumerate(lsq.response.replays) if item.valid)
    assert lsq.response.replays[bank].lq_idx_value==56 and trace.sq_head==64
    await trace.cycle(replay_ready=tuple(b==bank for b in range(3)))
    if wake=="pool_credit":await trace.write_all((127,))
    await issue(loads[-1],feedback=True)
    assert trace.sq_head==64 and all(trace.stores[p]["consumed"]==set() for p in range(64,128))
    await trace.idle(12)
    assert all(s["completed"] for s in trace.loads)
    await trace.finish(pending=rob_pointer(start+186))
    assert trace.sq_head==128 and len(trace.fragments_fired)==128 and trace.load_released==57
    assert all(s["completed"] for s in trace.stores.values())
    lsq.emit("RAW_exclusive128_real_original_effects",wake=wake,lane=lane,Stores=128,Loads=57,
             real_RAW_records=56,original_RAW_CAPACITY_slot_feedback=True,first_half_SQ_release=64,
             Load_feedback_before_second_half_Sbuffer_consumption=True,absolute_ROB_span_below320=True)
