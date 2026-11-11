"""Common system reset closes external jobs explicitly, not by fake responses."""

from dataclasses import asdict, replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs, lane_bypass, exception
from suites.memblock.lsq.testbenches.load_queue.transactions import Bypass
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Bus
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.special_owners import SpecialStore
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.uncache_recovery import UncacheRecoveryOwners


@pytest.mark.parametrize("phase", ("load_buffered_nc", "load_serial_nc", "load_serial_mmio", "load_full_nc", "load_bypass_s1", "store_serial_io", "store_serial_nc"))
async def test_common_system_reset_shared_pending_owner_then_same_load_store_slots_really_finish(lsq, phase):
    store_side = phase.startswith("store_")
    old_count = 16 if phase == "load_full_nc" else 1
    source = UncacheRecoveryOwners(lsq, kind="mmio_memory" if phase == "load_serial_mmio" else "nc")
    base = Inputs(pending=RobPtr.encode(10),pending_next=RobPtr.encode(10),bus=Bus(outstanding=phase=="load_full_nc"))
    store = SpecialStore(0,RobPtr.encode(10),0x20000,0xA020000,value=0x8877665544332211,
                         memory=(1 if phase=="store_serial_nc" else 7) if store_side else 0)
    loads = [cached_load(0,11,1,0x500000,0xC500000)] if store_side else [source.make_load(pos) for pos in range(old_count)]
    if store_side:
        loads = [replace(load,execution=replace(load.execution,need_replay=True,causes=1<<Cause.TLB_MISS,tlb_id=9)) for load in loads]
    dispatch = [Dispatch(True,2,store.rob,1,store_end=SqPtr.encode(1))]
    dispatch += [Dispatch(True,1,load.execution.uop.rob,1,load_start=load.execution.uop.lq) for load in loads]
    for first in range(0,len(dispatch),8):
        batch=dispatch[first:first+8]
        await lsq.cycle(replace(base,dispatch=tuple(batch)+(Dispatch(),)*(8-len(batch))))
    await lsq.cycle(replace(base,addresses=(store.address(),Address()),data=(Data(),store.data())))
    await lsq.cycle(replace(base,attributes=(store.attributes(),Attributes())))
    if phase=="load_serial_mmio":
        base=replace(base,pending=loads[0].execution.uop.rob,pending_next=loads[0].execution.uop.rob)
    for first in range(0,len(loads),3):
        batch=loads[first:first+3]
        await lsq.cycle(replace(base,loads=tuple(batch)+(Load(),)*(3-len(batch))))
    jobs=[]
    for sid in range(16 if phase=="load_full_nc" else 1):
        for _ in range(100):
            if lsq.response.uncache_request is not None:
                break
            await lsq.cycle(base)
        assert lsq.response.uncache_request is not None
        if phase=="load_buffered_nc":
            break
        assert lsq.response.uncache_request.cmd == int(store_side)
        mid = lsq.response.uncache_request.ident
        await lsq.cycle(replace(base,bus=replace(base.bus,ready=True)))
        jobs.append(dict(direction="store" if store_side else "load",mid=mid,sid=None,accepted_tick=lsq.last_tick,
                         externally_accepted_write=store_side))
        # NC Store ack would itself permit local completion. Reset the exact
        # accepted-but-not-ID-bound phase instead; IO/Load jobs bind normally.
        if phase!="store_serial_nc":
            await lsq.cycle(replace(base,bus=replace(base.bus,ack=True,ack_to_load=not store_side,mid=mid,sid=sid)))
            jobs[-1]["sid"]=sid
    if phase=="load_bypass_s1":
        await lsq.cycle(replace(base,bus=replace(base.bus,response=True,response_id=jobs[0]["sid"],data=0xFEDCBA9876543210,error=True,nderr=True)))
        jobs[0]["responded"]=True
        for _ in range(100):
            bank=next((bank for bank, item in enumerate(lsq.response.replays) if item.valid),None)
            if bank is not None:
                break
            await lsq.cycle(base)
        assert bank is not None
        await lsq.cycle(replace(base,replay_ready=tuple(source==bank for source in range(3))))
        await lsq.cycle(replace(base,bypass=(Bypass(True,loads[0].execution.uop.lq,True),Bypass(),Bypass())))
        lsq.expect(obs(bypass=lane_bypass(0, s1_valid=1, s1_paddr=loads[0].paddr),
            ld_exception=exception(valid=1, bus_error=1, access_fault=1)),
                   "old real bus response captured before reset; resetless data/exception history is still defined")
    assert not any(item.s2_valid for item in lsq.response.bypass)
    lsq.reach("LSQ-RESET.pending_store" if store_side else "LSQ-RESET.pending_load")
    lsq.emit("common_system_reset_external_jobs_aborted_not_returned", jobs=[job for job in jobs if not job.get("responded",False)],old_store=asdict(store),old_loads=[asdict(load) for load in loads],
             old_externally_accepted_writes_are_not_retracted=sum(job["externally_accepted_write"] for job in jobs),
             late_pre_reset_response_not_in_common_reset_contract=True)
    for edge in range(6):
        await lsq.cycle(replace(base,reset=True))
        if phase=="load_bypass_s1" and edge==0:
            lsq.expect(obs(bypass=lane_bypass(0, s2_valid=1, s2_data=0xFEDCBA9876543210*((1<<64)+1),
                s2_derr=1, s2_nderr=1), ld_exception=None),
                       "common reset does not erase the defined previous s1 data/error history")
    for _ in range(8):
        await lsq.cycle(base)
        assert lsq.response.uncache_request is None and not lsq.response.replay_allocate
        assert lsq.response.sbuffer_word_0 is None and lsq.response.mmio_stout is None
    trace=UncacheRecoveryOwners(lsq)
    trace.store=replace(trace.store,vaddr=0x30000,paddr=0xB030000,value=0x1122334455667788)
    new=[trace.make_load(pos) for pos in range(old_count)]
    # Same logical/physical LQ0.. and SQ0, but different PA/bytes/new UIDs.
    new=[replace(load,paddr=load.paddr+0x1000000,fullva=load.fullva+0x1000000,
                 execution=replace(load.execution,vaddr=load.fullva+0x1000000)) for load in new]
    await trace.dispatch(new,with_store=True)
    await trace.enqueue(list(range(old_count)))
    attempts=[await trace.transfer() for _ in range(old_count)]
    assert {a["mid"] for a in attempts}==set(range(old_count))
    await trace.consume_visible(range(old_count),0)
    await trace.finish()
    lsq.prove("LSQ-RESET.pending_store" if store_side else "LSQ-RESET.pending_load", "LSQ-RECOVER.reuse")
