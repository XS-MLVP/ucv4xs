"""Normal LDU routing, real recovery/reuse, and distinct STA-nuke control."""
from dataclasses import replace

import pytest

from lsqverify.lsq_wrapper.types import Address, Data
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr, RobPtr
from .ldu_rar_owners import LduRarOwners
from .memory_owners import StoreOwner, cached_load


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("window", ("current", "previous", "none"))
async def test_LDU_RAR_nuke_original_flushAfter_not_C_NK_and_same_slot_new_UID_completes(lsq, lane, window):
    if window != "none":
        lsq.reach("LSQ-RAR."+window+"_release")
    trace = LduRarOwners(lsq)
    old = cached_load(0, 10, 0, 0x24040, 0xC020040)
    young = cached_load(1, 11, 0, 0x35040, 0xC020040)
    trace.base = replace(trace.base, pending=old.execution.uop.rob, pending_next=old.execution.uop.rob)
    await trace.dispatch(loads=[old, young])
    await trace.pipeline(young, lane, release_window=window)
    nuke = await trace.pipeline(old, (lane+1)%3, expected_nuke=window != "none")
    if nuke:
        # Actual RAR response requests external ROB rollback; preserve old UID.
        lq, sq = await trace.cancel(old.execution.uop.rob, flush_self=False)
        assert lq == QueuePtr.encode(1) and sq == 0
        assert trace.loads[0]["completed"] and trace.loads[1]["cancelled"]
        new = cached_load(1, 12, 0, young.execution.vaddr, young.paddr)
        trace.base = replace(trace.base, pending=new.execution.uop.rob, pending_next=new.execution.uop.rob)
        await trace.dispatch(loads=[new])
        await trace.pipeline(new, (lane+2)%3)
    await trace.finish()
    if nuke:
        lsq.prove("LSQ-RAR."+window+"_release", "LSQ-RECOVER.partial", "LSQ-RECOVER.sent_load", "LSQ-RECOVER.reuse")
    lsq.emit("ldu_RAR_routing_case_complete", lane=lane, release_window=window,
             original_flushAfter=nuke, allocated=len(trace.loads),
             completed=sum(s["completed"] for s in trace.loads), cancelled=len(trace.cancelled),
             all_full_cycle_reference_compared=True)


@pytest.mark.parametrize("lane", range(3))
async def test_LDU_S3_cache_replay_revokes_previous_same_lane_RAR_RAW_then_original_slot_finishes(lsq, lane):
    lsq.reach("LSQ-RAR.revoke")
    trace = LduRarOwners(lsq)
    old = cached_load(0, 10, 0, 0x24040, 0xC020040)
    young = cached_load(1, 11, 0, 0x35040, 0xC020040)
    trace.base = replace(trace.base, pending=old.execution.uop.rob, pending_next=old.execution.uop.rob)
    await trace.dispatch(loads=[old, young])
    await trace.pipeline(young, lane, cause=Cause.CACHE_REPLAY, release_window="current")
    await trace.pipeline(old, (lane+1)%3)
    await trace.grant(young)
    await trace.pipeline(young, lane, feedback=True)
    await trace.finish()
    lsq.prove("LSQ-RAR.revoke")
    lsq.emit("ldu_RAR_revoke_case_complete", lane=lane, allocated=2, original_completed=2,
             original_query_revoke=True, original_slot_feedback=True, all_full_cycle_reference_compared=True)


@pytest.mark.parametrize("lane", range(3))
async def test_LDU_C_NK_requires_real_older_STA_not_RAR_response_and_both_original_owners_complete(lsq, lane):
    lsq.reach("LSQ-RETIRE.ordinary", "LSQ-RETIRE.rob_before_sbuffer")
    trace = LduRarOwners(lsq)
    store = StoreOwner(0, RobPtr.encode(10), 0x24040, 0xC020040)
    load = cached_load(0, 11, 1, store.vaddr, store.paddr)
    trace.base = replace(trace.base, pending=store.rob, pending_next=store.rob)
    await trace.dispatch(stores=[store], loads=[load])
    await trace.cycle(data=(store.data(), Data()))
    await trace.pipeline(load, lane, cause=Cause.VIOLATION,
                         s2_fields=dict(addresses=(store.address(), Address())))
    # Ordinary Store is now genuinely executed; ROB can retire it before SB.
    trace.base = replace(trace.base, pending=load.execution.uop.rob, pending_next=load.execution.uop.rob,
                         sbuffer_ready=(True, True))
    await trace.grant(load)
    await trace.pipeline(load, lane, feedback=True)
    await trace.finish()
    lsq.prove("LSQ-RETIRE.ordinary", "LSQ-RETIRE.rob_before_sbuffer")
    lsq.emit("ldu_STA_nuke_case_complete", lane=lane, original_load_completed=1, original_store_completed=1,
             original_store_fragment_consumed=len(trace.fragments_fired), cause=11,
             all_full_cycle_reference_compared=True)
