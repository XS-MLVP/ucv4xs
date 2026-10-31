"""Cases added AFTER the 5558-row lq-expanded-04 DA inventory review."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.actor import LoadActor
from suites.memblock.lsq.load_queue.types import Bus, Bypass, Inputs
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr, Store
from suites.memblock.lsq.replay.types import Cause, Refill, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import RobPtr


async def allocate(actor, count):
    uids = []
    for start in range(0, count, 8):
        uids.extend(await actor.dispatch((1,) * min(8, count - start)))
    return uids


async def test_every_dispatch_source_saves_all_virtual_slots_with_real_completion(lq):
    actor = LoadActor(lq)
    all_uids = []
    for lane in range(8):
        uids = []
        for count in (16,) * 7 + (8,):
            uids.extend(await actor.dispatch((count,), lanes=(lane,)))
        await actor.drain()
        assert set(uids) <= actor.completed
        all_uids.extend(uids)
    actor.checked(("LQ-ALLOC.all_lanes", "LQ-ALLOC.multi_flow", "LQ-ALLOC.wrap"), all_uids)


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("cause", (Cause.ADDRESS_DEPENDENCE, Cause.TLB_MISS, Cause.CACHE_MISS))
async def test_dependency_payload_for_every_replay_slot_from_every_s3_source(lq, lane, cause):
    actor = LoadActor(lq)
    uids = await allocate(actor, 120)
    for index, uid in enumerate(uids):
        owner = actor.owner(uid)
        owner.load = replace(owner.load, execution=replace(owner.load.execution, need_replay=True, causes=1 << cause,
                             address_sq=SqPtr.encode(7), data_sq=SqPtr.encode(7), tlb_id=index % 16, mshr=index % 16,
                             handled=cause == Cause.CACHE_MISS, last_beat=bool(index & 1)))
        await actor.execute([uid], lanes=(lane,))
    for _ in range(5):
        await actor.step()
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    if cause == Cause.ADDRESS_DEPENDENCE:
        await actor.step(Inputs(address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
    elif cause == Cause.TLB_MISS:
        await actor.step(Inputs(slow_tlb=TlbHint(True, 0, True)))
    else:
        for identity in range(0, 16, 2):
            await actor.step(Inputs(refills=(Refill(True, identity), Refill(True, identity + 1))))
    await actor.drain()
    assert {actor.owner(uid).feedback_slot for uid in uids} == set(range(120))
    actor.checked(("LQ-CAPACITY.replay_pool", "LQ-REPLAY.metadata"), uids)


async def test_real_head_near_candidates_in_last_age_slot_of_all_three_banks(lq):
    actor = LoadActor(lq)
    uids = await allocate(actor, 120)
    order = uids[3:] + uids[:3]
    for uid in order:
        owner = actor.owner(uid)
        owner.load = replace(owner.load, execution=replace(owner.load.execution, need_replay=True, causes=1 << Cause.BANK_CONFLICT))
        await actor.execute([uid])
    for _ in range(3):
        await actor.step()
    await actor.step(Inputs(replay_ready=(True,) * 3))
    assert [lq.observed[P.io(f"replay_{bank}_bits_replayQueueIdx")] for bank in range(3)] == [117, 118, 119]
    await actor.drain()
    actor.checked(("LQ-HEAD.replay_priority",), uids)


async def test_both_raw_store_lanes_select_all_physical_groups_with_original_metadata(lq):
    actor = LoadActor(lq)
    actor.rob_sequence = 2
    uids = await allocate(actor, 56)
    for uid in uids:
        o = actor.owner(uid)
        u = o.load.execution.uop
        await actor.step(Inputs(raw_queries=(RawQuery(True, o.rob, u.sq, o.load.paddr, 255, True, u.rvc, u.ftq, u.offset, u.checkpoint), RawQuery(), RawQuery())))
    await actor.step()
    for uid in uids:
        o = actor.owner(uid)
        stores = tuple(Store(True, RobPtr.encode(lane), o.load.paddr, 255, ftq_value=40 + lane, ftq_offset=20 + lane) for lane in range(2))
        await actor.step(Inputs(stores=stores))
        await actor.step()
        await actor.step()
        for lane in range(2):
            p = P.io(f"nuke_rollback_{lane}_")
            assert lq.observed[p + "valid"] and lq.observed[p + "bits_robIdx_value"] == o.rob.value
            assert lq.observed[p + "bits_stFtqIdx_value"] == 40 + lane
    await actor.drain(controls=Inputs(address_ready=SqPtr.encode(11)))
    actor.checked(("LQ-RAW.all_slots", "LQ-RAW.dual_store"), uids)


async def test_three_lane_uncache_sorted_payload_and_parallel_bypass_consumption(lq):
    actor = LoadActor(lq)
    uids = []
    for _ in range(2):
        uids.extend(await actor.dispatch((1,) * 8, configure=lambda load: replace(load, execution=replace(load.execution, need_replay=True, causes=1, nc=True))))
    for offset in range(0, 16, 3):
        batch = uids[offset:offset + 3]
        await actor.execute(batch[::-1])
    for _ in range(3):
        await actor.step()
    data = {}
    for sid in range(16):
        for _ in range(80):
            if lq.observed[P.p_uncache_req_valid]:
                break
            await actor.step()
        owner = next(actor.owner(uid) for uid in uids if actor.owner(uid).load.paddr == lq.observed[P.p_uncache_req_bits_addr])
        mid = lq.observed[P.p_uncache_req_bits_id]
        value = 0xFEDCBA9876000000 | owner.uid
        data[owner.uid] = value
        await actor.step(Inputs(bus=Bus(ready=True)))
        await actor.step(Inputs(bus=Bus(ack=True, mid=mid, sid=sid)))
        await actor.step(Inputs(bus=Bus(response=True, response_id=sid, data=value, error=bool(owner.uid & 1), nderr=bool(owner.uid & 2))))
    for _ in range(100):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        if set(uids) <= set(actor.issued):
            break
    assert set(uids) <= set(actor.issued)
    for offset in range(0, 16, 3):
        batch = uids[offset:offset + 3]
        queries = tuple(Bypass(True, actor.owner(uid).load.execution.uop.lq, True) for uid in batch)
        await actor.step(Inputs(bypass=queries + (Bypass(),) * (3 - len(queries))))
        await actor.step()
        for lane, uid in enumerate(batch):
            assert lq.observed[P.io(f"bypass_{lane}_s2Resp_valid")] and lq.observed[P.io(f"bypass_{lane}_s2Resp_bits_data")] == data[uid] * ((1 << 64) + 1)
        await actor.feedback(batch)
    await actor.drain()
    actor.checked(("LQ-UNCACHE.all_entries", "LQ-UNCACHE.bypass"), uids)
