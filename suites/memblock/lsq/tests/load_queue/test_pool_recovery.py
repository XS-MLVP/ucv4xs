"""Remaining DA: batch return lanes, strict write priority, every entry cancel.

All stimuli are public dispatch/S3/query/bus/redirect transactions. Even the
all-entry cancel tests refill the real pool and finish new owners afterwards.
"""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.recovery import RecoveringActor
from suites.memblock.lsq.load_queue.types import Bus, Bypass, Inputs, Load
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect


async def allocate(actor, count, configure=None):
    result = []
    for start in range(0, count, 8):
        result.extend(await actor.dispatch((1,) * min(8, count - start), configure=configure))
    return result


async def query_and_replay(actor, uids, *, rar_count, raw_count, replay_head=True):
    # Keep the oldest LQ slot out of RAR, as required by the real VLQ head.
    for offset in range(0, len(uids), 3):
        loads, rars, raws = [], [], []
        for uid in uids[offset:offset + 3]:
            if uid == uids[0] and not replay_head:
                continue
            owner = actor.owner(uid)
            owner.load = replace(owner.load, execution=replace(owner.load.execution, need_replay=True,
                                 causes=1 << Cause.TLB_MISS, tlb_id=15))
            loads.append(owner.load)
        for uid in uids[1 + offset:1 + min(offset + 3, rar_count)]:
            owner = actor.owner(uid)
            rars.append(RarQuery(True, owner.rob, QueuePtr.encode(owner.position), owner.load.paddr, True, True))
        for uid in uids[1 + offset:1 + min(offset + 3, raw_count)]:
            owner = actor.owner(uid)
            raws.append(RawQuery(True, owner.rob, owner.load.execution.uop.sq, owner.load.paddr, 255, True))
        await actor.step(Inputs(loads=tuple(loads) + (Load(),) * (3 - len(loads)),
                               rar_queries=tuple(rars) + (RarQuery(),) * (3 - len(rars)),
                               raw_queries=tuple(raws) + (RawQuery(),) * (3 - len(raws))))


@pytest.mark.parametrize("prefix", range(4))
async def test_full_real_pools_batched_cancel_at_each_return_alignment(lq, prefix):
    actor = RecoveringActor(lq)
    if prefix:
        prelude = await allocate(actor, prefix + 1)
        await query_and_replay(actor, prelude, rar_count=prefix, raw_count=prefix, replay_head=False)
        # No synthetic internal wake: use the external broadcast TLB response.
        await actor.step(Inputs(slow_tlb=TlbHint(True, 15, True)))
        await actor.drain()
    cancelled = []
    for _ in range(2):
        old = await allocate(actor, 120)
        await query_and_replay(actor, old, rar_count=96, raw_count=56)
        for _ in range(4):
            await actor.step()
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
        await actor.step(Inputs(redirect=Redirect(True, actor.owner(old[0]).rob, True)))
        await actor.settle()
        cancelled.extend(old)
        new = await allocate(actor, 120)
        await actor.drain()
        assert set(new) <= actor.completed
    actor.prove_reuse(("LQ-RECOVER.all", "LQ-RECOVER.reuse"), cancelled)


@pytest.mark.parametrize("prefix", range(3))
@pytest.mark.parametrize("strict", (False, True))
async def test_three_simultaneous_address_waits_preserve_all_120_dependency_owners(lq, strict, prefix):
    actor = RecoveringActor(lq)
    if prefix:
        initial = await allocate(actor, prefix, lambda load: replace(load, execution=replace(load.execution,
                                 need_replay=True, causes=1 << Cause.BANK_CONFLICT)))
        await actor.execute(initial)
        await actor.drain()
    def configure(load):
        return replace(load, execution=replace(load.execution, uop=replace(load.execution.uop, strict=strict,
                       load_wait=True, store_set_hit=True), need_replay=True, causes=1 << Cause.ADDRESS_DEPENDENCE,
                       address_sq=SqPtr.encode(7)))
    uids = await allocate(actor, 120, configure)
    for offset in range(0, 120, 3):
        await actor.execute(uids[offset:offset + 3])
    for _ in range(5):
        await actor.step()
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await actor.step(Inputs(address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
    await actor.drain()
    assert {actor.owner(uid).feedback_slot for uid in uids} == set(range(120))
    actor.checked(("LQ-STORE.address", "LQ-CAPACITY.replay_pool") + (("LQ-STORE.strict",) if strict else ()), uids)


def uncache_load(load, nc=True):
    return replace(load, execution=replace(load.execution, need_replay=True, causes=1, nc=nc), mmio=not nc)


async def enqueue_full_uncache(actor, *, nc=True, count=16):
    uids = await allocate(actor, count, lambda load: uncache_load(load, nc))
    for offset in range(0, count, 3):
        await actor.execute(uids[offset:offset + 3])
    for _ in range(4):
        await actor.step()
    return uids


async def accept_all_bus(actor, uids):
    jobs = {}
    for sid in range(len(uids)):
        for _ in range(80):
            if actor.env.observed[P.p_uncache_req_valid]:
                break
            await actor.step()
        post = actor.env.observed
        assert post[P.p_uncache_req_valid]
        owner = next(actor.owner(uid) for uid in uids if actor.owner(uid).load.paddr == post[P.p_uncache_req_bits_addr])
        mid = post[P.p_uncache_req_bits_id]
        assert mid not in jobs and owner.uid not in {job["uid"] for job in jobs.values()}
        await actor.step(Inputs(bus=Bus(ready=True)))
        await actor.step(Inputs(bus=Bus(ack=True, mid=mid, sid=sid)))
        jobs[mid] = dict(uid=owner.uid, sid=sid, data=0xBCDEFFED00000000 | owner.uid)
    assert len(jobs) == len(uids) and all(0 <= mid < 16 for mid in jobs)
    if len(uids) == 16:
        assert set(jobs) == set(range(16))
    return jobs


async def finish_refilled_uncache(actor, count=16):
    uids = await enqueue_full_uncache(actor, count=count)
    jobs = await accept_all_bus(actor, uids)
    for job in jobs.values():
        await actor.step(Inputs(bus=Bus(response=True, response_id=job["sid"], data=job["data"],
                                       error=bool(job["uid"] & 1), nderr=bool(job["uid"] & 2))))
    for _ in range(100):
        await actor.step(Inputs(replay_ready=(True,) * 3))
        if set(uids) <= set(actor.issued):
            break
    assert set(uids) <= set(actor.issued)
    by_uid = {job["uid"]: job for job in jobs.values()}
    for offset in range(0, count, 3):
        batch = uids[offset:offset + 3]
        queries = tuple(Bypass(True, actor.owner(uid).load.execution.uop.lq, True) for uid in batch)
        await actor.step(Inputs(bypass=queries + (Bypass(),) * (3 - len(queries))))
        await actor.step()
        for lane, uid in enumerate(batch):
            assert actor.env.observed[P.io(f"bypass_{lane}_s2Resp_valid")]
            assert actor.env.observed[P.io(f"bypass_{lane}_s2Resp_bits_data")] == by_uid[uid]["data"] * ((1 << 64) + 1)
        await actor.feedback(batch)
    await actor.drain()
    return uids


@pytest.mark.parametrize("phase", ("holding_mmio", "request_backpressure"))
@pytest.mark.parametrize("prefix", range(4))
async def test_all_uncache_entries_cancel_before_accept_then_full_pool_new_uid_finish(lq, phase, prefix):
    actor = RecoveringActor(lq)
    if prefix:
        await finish_refilled_uncache(actor, count=prefix)
    actor.rob_sequence = 10
    old = await enqueue_full_uncache(actor, nc=phase != "holding_mmio")
    assert bool(lq.observed[P.p_uncache_req_valid]) == (phase == "request_backpressure")
    buffered = {pin: lq.observed[pin] for pin in (P.p_uncache_req_bits_id, P.p_uncache_req_bits_addr)}
    await actor.step(Inputs(redirect=Redirect(True, actor.owner(old[0]).rob, True)))
    await actor.settle()
    for _ in range(6):
        await actor.step()
        assert not lq.observed[P.p_replayAllocate]
        if phase == "holding_mmio":
            assert not lq.observed[P.p_uncache_req_valid]
        else:
            # The child already fired into the real elastic request register.
            # It has no redirect input, so public top-level ready must accept
            # this stable old request and eventually return its response.
            assert lq.observed[P.p_uncache_req_valid] and all(lq.observed[pin] == value for pin, value in buffered.items())
    if phase == "request_backpressure":
        await actor.step(Inputs(bus=Bus(ready=True)))
        await actor.step(Inputs(bus=Bus(ack=True, mid=buffered[P.p_uncache_req_bits_id], sid=3)))
        await actor.step(Inputs(bus=Bus(response=True, response_id=3, data=0xCACE1, error=True)))
        for _ in range(6):
            await actor.step()
            assert not lq.observed[P.p_replayAllocate] and not lq.observed[P.p_uncache_req_valid]
    await finish_refilled_uncache(actor)
    actor.prove_reuse(("LQ-RECOVER.all", "LQ-RECOVER.reuse"), old)


@pytest.mark.parametrize("target_mid", range(16))
async def test_each_real_uncache_id_cancel_on_wakeup_then_return_all_and_refill(lq, target_mid):
    actor = RecoveringActor(lq)
    old = await enqueue_full_uncache(actor)
    jobs = await accept_all_bus(actor, old)
    target = jobs[target_mid]
    await actor.step(Inputs(bus=Bus(response=True, response_id=target["sid"], data=target["data"])))
    # The actual returned entry is now in wakeup. A shared redirect reaches
    # the real entry and Replay concurrently; it must not leave a live UID.
    await actor.step(Inputs(redirect=Redirect(True, actor.owner(old[0]).rob, True)))
    await actor.settle()
    for mid, job in jobs.items():
        if mid != target_mid:
            await actor.step(Inputs(bus=Bus(response=True, response_id=job["sid"], data=job["data"], error=True)))
    for _ in range(6):
        await actor.step()
        assert not lq.observed[P.p_replayAllocate] and not lq.observed[P.p_uncache_req_valid]
    await finish_refilled_uncache(actor)
    actor.prove_reuse(("LQ-RECOVER.sent_uncache", "LQ-RECOVER.reuse"), old)


async def test_second_std_wakeup_lane_unblocks_original_dependency(lq):
    actor = RecoveringActor(lq)
    uids = await allocate(actor, 3, lambda load: replace(load, execution=replace(load.execution, need_replay=True,
                          causes=1 << Cause.FORWARD_FAILURE, data_sq=SqPtr.encode(7))))
    await actor.execute(uids)
    for _ in range(5):
        await actor.step()
        assert not any(lq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await actor.step(Inputs(data_wakeups=(StoreWakeup(), StoreWakeup(True, SqPtr.encode(7)))))
    await actor.drain()
    actor.checked(("LQ-STORE.data",), uids)


async def test_mixed_non_address_lane0_and_two_strict_waits_keep_other_owners(lq):
    # lq-expanded-05 left 120 strict write-priority assignments unexecuted:
    # lane2+lane1 carry address waits while lane0 carries another real cause.
    # Allocate real new owners; this does NOT waive the disabled feedback case
    # that corrupts an already-live strict owner in test_replay.py.
    actor = RecoveringActor(lq)
    uids = await allocate(actor, 6)
    for index, uid in enumerate(uids):
        owner = actor.owner(uid)
        address_wait = bool(index % 3)
        owner.load = replace(owner.load, execution=replace(owner.load.execution,
                             uop=replace(owner.load.execution.uop, strict=address_wait, load_wait=address_wait),
                             need_replay=True, causes=1 << (Cause.ADDRESS_DEPENDENCE if address_wait else Cause.BANK_CONFLICT),
                             address_sq=SqPtr.encode(7)))
    await actor.execute(uids[:3])
    await actor.execute(uids[3:])
    for _ in range(5):
        await actor.step()
        assert not lq.observed[P.p_replay_1_valid] and not lq.observed[P.p_replay_2_valid]
    await actor.step(Inputs(address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
    await actor.drain()
    actor.checked(("LQ-STORE.strict", "LQ-REPLAY.causes"), uids)
