"""Exact full virtual SQ exclusive boundary, not a129th Store allocation."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.replay.types import Cause
from suites.memblock.lsq.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load


@pytest.mark.parametrize("count",(127,128))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("strict",(False,True))
async def test_full_virtual_sq_exclusive_endpoint_current_window_original_effects(lsq,count,lane,strict):
    trace=MemoryOwners(lsq)
    stores=[StoreOwner(pos,RobPtr.encode(10+pos),0x400000+pos*64,0xB400000+pos*64,
                       value=0x8877665500000000+pos) for pos in range(count)]
    source=stores[17]
    load=cached_load(0,10+count,count,source.vaddr,source.paddr)
    if strict:
        load=replace(load,execution=replace(load.execution,uop=replace(load.execution.uop,strict=True,load_wait=True,
                                                                      store_set_hit=True,wait_sq=SqPtr.encode(count-1))))
    await trace.dispatch(stores,[load])
    await trace.write_all(range(64))
    query=Query(True,load.execution.vaddr,load.execution.uop.sq,3,strict=strict)
    await trace.forward(load,lane,query=query)
    p=P.io(f"forward_{lane}_s2Resp_")
    lsq.expect({p+"valid":1,p+"bits_forwardInvalid":0,p+"bits_matchInvalid":0,
                p+"bits_dataInvalid_valid":0,p+"bits_addrInvalid_valid":int(strict)},
               "full exclusive SQ endpoint uses real current physical window, strict still waits")
    if strict:
        lsq.expect({p+"bits_addrInvalid_bits_first_flag":int(SqPtr.encode(count-1).first),
                    p+"bits_addrInvalid_bits_second_flag":int(SqPtr.encode(count-1).second),
                    p+"bits_addrInvalid_bits_value":SqPtr.encode(count-1).value},
                   "strict dependency retains original last virtual Store identity")
    for byte in range(16):
        lsq.expect({p+f"bits_forwardMask_{byte}":int(byte<8)},"no invented byte outside original Store")
        if byte<8:
            lsq.expect({p+f"bits_forwardData_{byte}":source.value>>(8*byte)&255},"original PA byte in current window")
    lsq.emit("sq_exact_endpoint_original_query",count=count,lane=lane,strict=strict,exclusive_boundary=count,
             physical_window=[0,64],source_position=source.position,load_completed=False)
    replay=replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.ADDRESS_DEPENDENCE,
                                         address_sq=SqPtr.encode(count-1),data_sq=SqPtr.encode(count-1)))
    if strict:
        await trace.execute([replay])
    # Only the first64 Stores have executed. ROB may retire that prefix, NOT
    # the still-unexecuted second physical window. Keep the actual full128
    # allocation; an independent audit rejected the old premature Load head.
    trace.base=replace(trace.base,pending=stores[64].rob,pending_next=stores[64].rob,sbuffer_ready=(True,True))
    for _ in range(180):
        await trace.cycle()
        if trace.sq_head==64:break
    assert trace.sq_head==64 and all(trace.stores[pos]["completed"] for pos in range(64))
    trace.base=replace(trace.base,sbuffer_ready=(False,False))
    await trace.write_all(range(64,count))
    trace.base=replace(trace.base,pending=load.execution.uop.rob,pending_next=load.execution.uop.rob,sbuffer_ready=(True,True))
    for _ in range(180):
        await trace.cycle()
        if trace.sq_head==count:break
    assert trace.sq_head==count
    if strict:
        await trace.replay_complete(replay)
    await trace.finish()
    assert len(trace.fragments_fired)==count and all(s["completed"] for s in trace.stores.values())
    assert all(s["completed"] for s in trace.loads)
    lsq.prove("LSQ-ALLOC.sq_capacity","LSQ-FORWARD.aligned")
