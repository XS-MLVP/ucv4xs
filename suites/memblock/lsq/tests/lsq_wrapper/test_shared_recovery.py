"""True both-branch cancellation, retired prefix walk, cross-page UQ and reset."""
from dataclasses import replace

import pytest

from lsqverify.rar.types import Query as RarQuery
from lsqverify.raw.types import Query as RawQuery
from lsqverify.replay.types import Cause, TlbHint
from lsqverify.vlq.types import QueuePtr, RobPtr
from .memory_owners import StoreOwner, cached_load
from .recovery_owners import RecoveryOwners


def stores(count, *, start=0, rob=10, page=False, tag=0):
    return [StoreOwner(start+offset, RobPtr.encode(rob+offset), 0x200000+(tag+offset)*8192+(4092 if page else 0),
                       0xA200000+(tag+offset)*8192+(4092 if page else 0), value=0x1122334400000000+tag+offset,
                       second_page=0xB400000+(tag+offset)*8192 if page else None) for offset in range(count)]


async def pool_queries(trace, loads):
    for offset in range(0, 96, 3):
        rars = tuple(RarQuery(True, load.execution.uop.rob, load.execution.uop.lq, load.paddr, True) for load in loads[1+offset:1+offset+3])
        raws = tuple(RawQuery(True, load.execution.uop.rob, load.execution.uop.sq, load.paddr, 255, True) for load in loads[offset:min(offset+3,56)]) if offset < 56 else ()
        await trace.cycle(rar_queries=rars, raw_queries=raws+(RawQuery(),)*(3-len(raws)))


@pytest.mark.parametrize("return_alignment", range(4))
async def test_both_real_branches_full_query_replay_pools_all_cancel_and_same_slot_new_uids(lsq, return_alignment):
    trace = RecoveryOwners(lsq)
    if return_alignment:
        trace.base = replace(trace.base, pending=RobPtr.encode(0), pending_next=RobPtr.encode(0))
        # Move public RAR/RAW freelist return alignment without a private poke.
        pre_s = stores(1, rob=1)
        pre_l = [cached_load(pos, 2+pos, 1, 0x400000+pos*64, 0xC400000+pos*64) for pos in range(return_alignment+1)]
        await trace.dispatch(pre_s, pre_l)
        await pool_queries_prefix(trace, pre_l, return_alignment)
        await trace.write_all()
        await trace.finish(pending=RobPtr.encode(9))
        trace.base = replace(trace.base, sbuffer_ready=(False, False))
    sq_start = return_alignment and 1 or 0
    lq_start = return_alignment+1 if return_alignment else 0
    old_s = stores(8, start=sq_start)
    old_l = [cached_load(lq_start+pos, 18+pos, sq_start+8, 0x500000+pos*64, 0xC500000+pos*64) for pos in range(120)]
    old_l = [replace(load, execution=replace(load.execution, need_replay=True, causes=1<<Cause.TLB_MISS, tlb_id=9)) for load in old_l]
    await trace.dispatch(old_s, old_l)
    # Leave the oldest actual Store address missing: real SQ ready must not
    # reclaim RAW before the intended full-pool shared cancellation.
    await trace.write_all(range(sq_start+1, sq_start+8))
    await pool_queries(trace, old_l)
    await trace.execute(old_l)
    await trace.idle(5)
    assert not any(lsq.observed[f"io_replay_{bank}_valid"] for bank in range(3))
    assert await trace.cancel(old_s[0].rob) == (QueuePtr.encode(lq_start), sq_start)
    new_s = stores(8, start=sq_start, tag=64)
    new_l = [replace(load, execution=replace(load.execution, causes=1<<Cause.BANK_CONFLICT),
                     paddr=load.paddr+0x1000000, fullva=load.fullva+0x1000000) for load in old_l]
    new_l = [replace(load, execution=replace(load.execution, vaddr=load.fullva)) for load in new_l]
    await trace.dispatch(new_s, new_l)
    await pool_queries(trace, new_l)
    await trace.execute(new_l)
    await trace.write_all(range(sq_start, sq_start+8))
    for load in new_l:
        # Fair held-candidate consumer: grant any visible original UID, not a
        # fixed program-order request that may be behind a held selection.
        visible = None
        for _ in range(100):
            for bank in range(3):
                if lsq.observed[f"io_replay_{bank}_valid"]:
                    key = QueuePtr(bool(lsq.observed[f"io_replay_{bank}_bits_uop_lqIdx_flag"]), lsq.observed[f"io_replay_{bank}_bits_uop_lqIdx_value"])
                    visible = trace.active_loads[key]["load"]
                    break
            if visible is not None:
                break
            await trace.cycle()
        assert visible is not None
        await trace.replay_complete(visible)
    await trace.finish(pending=RobPtr.encode(138))
    lsq.prove("LSQ-RECOVER.all", "LSQ-RECOVER.reuse")


async def pool_queries_prefix(trace, loads, count):
    for load in loads[1:count+1]:
        await trace.cycle(rar_queries=(RarQuery(True, load.execution.uop.rob, load.execution.uop.lq, load.paddr, True),RarQuery(),RarQuery()),
                          raw_queries=(RawQuery(True,load.execution.uop.rob,load.execution.uop.sq,load.paddr,255,True),RawQuery(),RawQuery()))


async def test_shared_redirect_after_ten_retired_store_prefix_walk_preserves_old_bytes_and_sq11(lsq):
    trace = RecoveryOwners(lsq)
    old_s = stores(14)
    old_l = [cached_load(pos, 24+pos, 14, 0x500000+pos*64, 0xC500000+pos*64) for pos in range(2)]
    old_l = [replace(load, execution=replace(load.execution, need_replay=True, causes=1<<Cause.TLB_MISS, tlb_id=9)) for load in old_l]
    await trace.dispatch(old_s, old_l)
    await trace.write_all()
    await trace.execute(old_l)
    trace.base = replace(trace.base, pending=old_s[10].rob, pending_next=old_s[10].rob)
    await trace.cycle()
    assert await trace.cancel(old_s[10].rob, flush_self=False) == (QueuePtr.encode(0), 11)
    new_s = stores(3, start=11, rob=21, tag=64)
    new_l = [cached_load(pos,24+pos,14,0x600000+pos*64,0xD600000+pos*64) for pos in range(2)]
    await trace.dispatch(new_s, new_l)
    await trace.write_all(range(11,14))
    await trace.finish(pending=RobPtr.encode(26))
    lsq.prove("LSQ-RECOVER.partial", "LSQ-RECOVER.retired_store", "LSQ-RECOVER.reuse")


@pytest.mark.parametrize("cancel_all", (False, True))
async def test_two_real_cross_page_uq_cancel_suffix_and_same_slot_page_fragments_complete(lsq, cancel_all):
    trace = RecoveryOwners(lsq)
    old_s = stores(2, page=True)
    old_l = [cached_load(0,12,2,0x600000,0xD600000)]
    await trace.dispatch(old_s, old_l)
    await trace.write_all()
    cutoff = old_s[0].rob
    first = 0 if cancel_all else 1
    assert await trace.cancel(cutoff, flush_self=cancel_all) == (QueuePtr.encode(0), first)
    new_s = stores(2-first,start=first,rob=10+first,page=True,tag=64)
    new_l = [cached_load(0,12,2,0x700000,0xE700000)]
    await trace.dispatch(new_s,new_l)
    await trace.write_all(range(first,2))
    await trace.finish(pending=RobPtr.encode(13))
    lsq.prove("LSQ-RECOVER.reuse", "LSQ-RECOVER.all" if cancel_all else "LSQ-RECOVER.partial")


@pytest.mark.parametrize("phase", ("allocated", "s2_inflight", "tlb_wait", "replay_selected", "replay_granted", "sbuffer"))
async def test_active_shared_reset_both_branches_original_uids_abort_and_same_slots_finish(lsq, phase):
    trace = RecoveryOwners(lsq)
    old_s = stores(2)
    old_l = [cached_load(pos,12+pos,2,0x500000+pos*64,0xC500000+pos*64) for pos in range(2)]
    cause = Cause.TLB_MISS if phase in ("tlb_wait", "sbuffer") else Cause.BANK_CONFLICT
    old_l = [replace(load,execution=replace(load.execution,need_replay=True,causes=1<<cause,tlb_id=9)) for load in old_l]
    await trace.dispatch(old_s,old_l)
    if phase == "s2_inflight":
        await trace.write(0)
    elif phase != "allocated":
        await trace.write_all()
    if phase not in ("allocated","s2_inflight"):
        await trace.execute(old_l)
        await trace.idle(6)
    if phase == "replay_granted":
        await trace.cycle(replay_ready=(True,True,True))
        assert any("grant" in state for state in trace.loads)
    if phase == "replay_selected":
        assert any(lsq.observed[f"io_replay_{bank}_valid"] for bank in range(3))
    if phase == "sbuffer":
        trace.base = replace(trace.base,pending=old_l[0].execution.uop.rob,pending_next=old_l[0].execution.uop.rob)
        for _ in range(40):
            await trace.cycle()
            if lsq.observed["io_sbuffer_req_0_valid"]:
                break
        assert lsq.observed["io_sbuffer_req_0_valid"] and not trace.fragments_fired
    lsq.reach("LSQ-RESET.active_load", "LSQ-RESET.active_store")
    await trace.reset()
    trace.base = replace(trace.base,pending=RobPtr.encode(9),pending_next=RobPtr.encode(9))
    new_s = stores(2,tag=64)
    new_l = [cached_load(pos,12+pos,2,0x600000+pos*64,0xD600000+pos*64) for pos in range(2)]
    await trace.dispatch(new_s,new_l)
    await trace.write_all()
    await trace.finish(pending=RobPtr.encode(14))
    lsq.prove("LSQ-RESET.active_load", "LSQ-RESET.active_store", "LSQ-RECOVER.reuse")
