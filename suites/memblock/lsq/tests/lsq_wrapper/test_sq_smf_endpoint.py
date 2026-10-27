"""Actual multi-match query -> Replay waits for full original SQ boundary."""
from dataclasses import replace

import pytest

from lsqverify.replay.types import Cause
from lsqverify.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load


@pytest.mark.parametrize("count",(127,128))
@pytest.mark.parametrize("lane",range(3))
async def test_smf_full_exclusive_sq_waits_until_all_original_store_effects(lsq,count,lane):
    trace=MemoryOwners(lsq)
    stores=[StoreOwner(pos,RobPtr.encode(10+pos),0x400000+pos*64,0xB400000+pos*64,
                       value=0x8877665500000000+pos) for pos in range(count)]
    stores[0]=replace(stores[0],size=0,value=0x11)
    stores[1]=replace(stores[1],vaddr=stores[0].vaddr+1,paddr=stores[0].paddr+1,size=0,value=0x22)
    load=cached_load(0,10+count,count,stores[0].vaddr,stores[0].paddr)
    await trace.dispatch(stores,[load])
    await trace.write_all(range(64))
    await trace.forward(load,lane)
    p=f"io_forward_{lane}_s2Resp_"
    lsq.expect({p+"valid":1,p+"bits_forwardInvalid":1,p+"bits_addrInvalid_valid":0,p+"bits_dataInvalid_valid":0},
               "two real partial Store sources require SMF replay, not successful Load data")
    replay=replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.STORE_MULTI_MATCH))
    await trace.execute([replay])

    async def blocked_edge():
        await trace.cycle()
        if trace.sq_head<count:
            lsq.expect({f"io_replay_{bank}_valid":0 for bank in range(3)},
                       "SMF original exclusive boundary still has unconsumed older Stores")

    for _ in range(4):await blocked_edge()
    trace.base=replace(trace.base,pending=stores[64].rob,pending_next=stores[64].rob,sbuffer_ready=(True,True))
    for _ in range(180):
        await blocked_edge()
        if trace.sq_head==64:break
    assert trace.sq_head==64
    trace.base=replace(trace.base,sbuffer_ready=(False,False))
    await trace.write_all(range(64,count))
    for _ in range(4):await blocked_edge()
    trace.base=replace(trace.base,pending=load.execution.uop.rob,pending_next=load.execution.uop.rob,sbuffer_ready=(True,True))
    for _ in range(180):
        await blocked_edge()
        if trace.sq_head==count:break
    assert trace.sq_head==count and all(s["completed"] for s in trace.stores.values())
    await trace.replay_complete(replay)
    await trace.finish()
    assert all(s["completed"] for s in trace.loads) and len(trace.fragments_fired)==count
    lsq.emit("sq_smf_full_endpoint_original_completion",count=count,lane=lane,original_slot_feedback=True,
             scope="actual multi-match held until all original Store effects; not full random/STRESS signoff")
