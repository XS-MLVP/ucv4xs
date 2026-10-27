"""Same18 original RAR routing/capacity programs, corrected native S3 fields."""
from dataclasses import replace

import pytest

from lsqverify.lsq_wrapper.types import Address, Data
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr, RobPtr
from .ldu_s3_owners import LduS3RarOwners as LduRarOwners
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
    trace.base = replace(trace.base, pending=load.execution.uop.rob, pending_next=load.execution.uop.rob,
                         sbuffer_ready=(True, True))
    await trace.grant(load)
    await trace.pipeline(load, lane, feedback=True)
    await trace.finish()
    lsq.prove("LSQ-RETIRE.ordinary", "LSQ-RETIRE.rob_before_sbuffer")
    lsq.emit("ldu_STA_nuke_case_complete", lane=lane, original_load_completed=1, original_store_completed=1,
             original_store_fragment_consumed=len(trace.fragments_fired), cause=11,
             all_full_cycle_reference_compared=True)


@pytest.mark.parametrize("lane_rotation", range(3))
async def test_LDU_full_96_RAR_original_readers_oldest_query_needs_no_allocation_then_all_97_dequeue(lsq, lane_rotation):
    lsq.reach("LSQ-RAR.head_reclaim")
    trace = LduRarOwners(lsq)
    loads = [cached_load(n, 10+n, 0, 0x40000+64*n, 0xD000000+64*n) for n in range(97)]
    trace.base = replace(trace.base, pending=loads[0].execution.uop.rob, pending_next=loads[0].execution.uop.rob)
    await trace.dispatch(loads=loads)
    for n, load in enumerate(loads[1:]):
        await trace.pipeline(load, (n+lane_rotation)%3)
        assert not lsq.observed["io_toLsqEnqCtrl_lqDeq_valid"] and not lsq.observed["io_lqEmpty"]
    assert not trace.loads[0]["sent"] and all(s["sent"] and not s["completed"] for s in trace.loads[1:])
    lsq.emit("ldu_full_RAR_public_ownership", original_young_readers=96, oldest_UID=trace.loads[0]["uid"],
             head_releases=0, revokes=0, redirects=0, all_young_S3_returned=True,
             scope="96 accepted distinct younger queries, no internal slot reads")
    await trace.pipeline(loads[0], 2)
    await trace.finish()
    assert len(trace.loads)==97 and all(s["completed"] for s in trace.loads)
    lsq.prove("LSQ-RAR.head_reclaim")
    lsq.emit("ldu_full_RAR_original_97_complete", allocated=97, completed=97,
             full_cycle_reference_compared=True, source_scope="aligned_cached_hit_no_release_no_alias")
