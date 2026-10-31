"""First gap expansion over all native input lanes and dependency families."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr
from suites.memblock.lsq.replay.types import Cause, Enqueue, L2Hint, LqWakeup, Refill, StoreWakeup, TlbHint


async def unblock(env, req):
    cause = req.causes.bit_length() - 1
    if cause == Cause.UNCACHE:
        await env.cycle(mmio=LqWakeup(True, req.uop.lq))
    elif cause == Cause.STORE_MULTI_MATCH:
        await env.cycle(dequeue=req.uop.sq)
    elif cause == Cause.ADDRESS_DEPENDENCE:
        await env.cycle(address_ready=SqPtr.encode(8))
    elif cause == Cause.TLB_MISS:
        await env.cycle(fast_tlb=TlbHint(True, req.tlb_id))
    elif cause == Cause.FORWARD_FAILURE:
        await env.cycle(data_bits=1 << req.data_sq.value)
    elif cause == Cause.CACHE_MISS:
        await env.cycle(refills=(Refill(True, req.mshr), Refill()))
    elif cause == Cause.RAR_CAPACITY:
        await env.cycle(rar_full=False)
    elif cause == Cause.RAW_CAPACITY:
        await env.cycle(raw_full=False)


@pytest.mark.parametrize("cause", range(12))
async def test_each_supported_cause_waits_for_its_dependency(replay, cause):
    env = replay
    await env.cycle(rar_full=True, raw_full=True)
    req = env.request(cause, tag=cause + 1)
    await env.cycle({cause % 3: req})
    uid = env.uid(req)
    if cause not in (5, 7, 8, 11):
        await env.idle(6)
        assert not any(env.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
        await unblock(env, req)
    env.arm("LRQ-PERF.events", [uid])
    await env.complete(lane=(cause + 1) % 3)


@pytest.mark.parametrize("lane", range(3))
async def test_three_lanes_sparse_banks_and_vector_payload(replay, lane):
    env = replay
    reqs = [env.request(tag=17 + i, lq=40 + i, rob=20 + i, vector=bool(i % 2), aligned_type=i + 1, mask=0xA35C ^ (i << 12)) for i in range(3)]
    reqs = [replace(req, uop=replace(req.uop, exceptions=sum(1 << bit for bit in (23, 19, 15, 7, 6)))) for req in reqs]
    await env.cycle({lane: reqs[0]})
    await env.cycle({(lane + 1) % 3: reqs[1], (lane + 2) % 3: reqs[2]})
    uids = [env.uid(req) for req in reqs]
    env.arm(("LRQ-HOLD.stable", "LRQ-PAYLOAD.exceptions", "LRQ-PERF.events"), uids)
    await env.idle(8)
    assert all(env.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await env.issue_all()
    await env.release_all()


@pytest.mark.parametrize("size", range(4))
async def test_scalar_access_size_and_sixteen_byte_offsets(replay, size):
    env = replay
    for offset in range(16):
        req = env.request(tag=offset + 64, lq=offset + 40)
        req = replace(req, vaddr=(req.vaddr & ~15) | offset, uop=replace(req.uop, operation=size << 1))
        await env.cycle({offset % 3: req})
        await env.complete(lane=(offset + 1) % 3)


@pytest.mark.parametrize("method", ("address_pointer", "address_bits", "address_wakeup", "data_pointer", "data_wakeup", "actual_write", "sq_empty"))
async def test_store_dependency_public_ready_paths(replay, method):
    env = replay
    address = method.startswith("address")
    req = env.request(Cause.ADDRESS_DEPENDENCE if address else Cause.FORWARD_FAILURE)
    await env.cycle({2: req}, upper=SqPtr.encode(64))
    uid = env.uid(req)
    await env.idle(5)
    assert not env.observed[P.p_replay_0_valid]
    env.arm("LRQ-STORE." + method, [uid])
    if method == "address_pointer":
        await env.cycle(address_ready=SqPtr.encode(8))
    elif method == "address_bits":
        await env.cycle(address_bits=1 << 7)
    elif method == "address_wakeup":
        await env.cycle(address_wakeups=(StoreWakeup(), StoreWakeup(True, SqPtr.encode(7))))
    elif method == "data_pointer":
        await env.cycle(data_ready=SqPtr.encode(8))
    elif method == "data_wakeup":
        await env.cycle(data_wakeups=(StoreWakeup(), StoreWakeup(True, SqPtr.encode(7))))
    elif method == "actual_write":
        # Existing owners use ready state, while this is specifically the NEW
        # enqueue fast path. Feed the issued owner back into FF with a real write.
        await env.cycle(data_bits=1 << 7)
        slot, uid = await env.issue()
        await env.cycle(data_bits=0)
        updated = replace(req, vaddr=req.vaddr + 16)
        await env.cycle({1: replace(updated, replay_feedback=True, slot=slot)}, data_writes=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup()))
    else:
        await env.cycle(sq_empty=True)
    await env.complete()


async def test_strict_and_physical_store_wakeup_window(replay):
    env = replay
    req = env.request(Cause.ADDRESS_DEPENDENCE)
    req = replace(req, uop=replace(req.uop, strict=True, load_wait=True, store_set_hit=True))
    await env.cycle({0: req}, upper=SqPtr.encode(64), address_bits=1 << 7)
    uid = env.uid(req)
    await env.idle(6)
    assert not env.observed[P.p_replay_0_valid]
    # A matching SQ wakeup outside the current 64-item physical queue cannot
    # unblock this strict dependency. Reset the physical head, then real wake.
    await env.cycle(dequeue=SqPtr.encode(8), address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup()))
    await env.idle(4)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(dequeue=SqPtr.encode(0), address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup()))
    env.arm(("LRQ-STORE.strict", "LRQ-STORE.address_wakeup"), [uid])
    await env.complete()


@pytest.mark.parametrize("base", (63, 127, 191, 255))
async def test_sq_flag_rollover_controls_dependency(replay, base):
    env = replay
    req = env.request(Cause.FORWARD_FAILURE, sq=base)
    await env.cycle({1: req}, data_ready=SqPtr.encode(base), dequeue=SqPtr.encode(base - 1))
    uid = env.uid(req)
    await env.idle(4)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(data_ready=SqPtr.encode(base + 1))
    env.arm("LRQ-STORE.wrap", [uid])
    await env.complete()


@pytest.mark.parametrize("fast", (False, True))
async def test_all_tlb_ids_and_broadcast_or_full_fast_paths(replay, fast):
    env = replay
    for identity in range(16):
        req = env.request(Cause.TLB_MISS, tlb_id=identity, tag=identity + 1)
        await env.cycle({identity % 3: req})
        uid = env.uid(req)
        await env.idle(3)
        assert not any(env.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
        if fast:
            await env.cycle(fast_tlb=TlbHint(True, identity))
        else:
            await env.cycle(slow_tlb=TlbHint(True, identity ^ 1, True))
        env.arm("LRQ-TLB.fast" if fast else "LRQ-TLB.all", [uid])
        await env.complete()
    req = env.request(Cause.TLB_MISS, tlb_full=True)
    await env.cycle({0: req})
    env.arm("LRQ-TLB.full", [env.uid(req)])
    await env.complete()


@pytest.mark.parametrize("last", (False, True))
@pytest.mark.parametrize("keyword", (False, True))
@pytest.mark.parametrize("channel", (0, 1))
async def test_l2_hint_channel_keyword_and_last_beat(replay, last, keyword, channel):
    env = replay
    req = env.request(Cause.CACHE_MISS, last_beat=last, mshr=15 if channel else 0)
    await env.cycle({channel: req})
    uid = env.uid(req)
    await env.idle(5)
    hints = tuple(L2Hint(True, req.mshr, keyword) if i == channel else L2Hint() for i in range(2))
    await env.cycle(l2_hints=hints)
    env.arm(("LRQ-REFILL.beats", "LRQ-REFILL.channels"), [uid])
    await env.complete()


async def test_replay_feedback_changes_cause_without_new_allocation(replay):
    env = replay
    req = env.request(Cause.BANK_CONFLICT, lq=40)
    await env.cycle({2: req})
    slot, uid = await env.issue()
    updated = env.request(Cause.TLB_MISS, lq=40, tag=7, tlb_id=15)
    await env.feedback(slot, lane=1, again=updated)
    assert len(env.model.owners) == 1 and env.model.sequence == 1
    await env.idle(5)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(fast_tlb=TlbHint(True, 15))
    await env.complete(slot, lane=0)
    assert uid in env.coverage.completed


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("cause", (Cause.BANK_CONFLICT, Cause.ADDRESS_DEPENDENCE))
async def test_every_slot_from_each_input_then_two_full_pool_rounds(replay, lane, cause):
    env = replay
    all_uids = []
    for round_id in range(2):
        await env.cycle(ready=(False,) * 3, writeback=QueuePtr.encode(120 * round_id), address_ready=SqPtr.encode(0))
        for slot in range(120):
            req = env.request(cause if not round_id else Cause.BANK_CONFLICT, rob=20 + slot,
                              lq=120 * round_id + slot, tag=slot + round_id * 120 + 1, mshr=slot % 16,
                              vector=bool(slot % 2), aligned_type=slot % 8, mask=(slot * 439) & 65535)
            req = replace(req, uop=replace(req.uop, strict=bool(slot % 2), exceptions=(1 << 23) | (1 << 6)))
            await env.cycle({lane: req})
            assert env.model.owners[next(tx["slot"] for tx in env.last_change["allocated"])].input_lane == lane
        assert env.observed[P.p_lqFull] and len(env.model.owners) == 120
        uids = [owner.uid for owner in env.model.owners.values()]
        all_uids.extend(uids)
        env.arm(("LRQ-RECYCLE.full", "LRQ-RECYCLE.banks", "LRQ-PAYLOAD.metadata", "LRQ-PERF.events"), uids)
        if cause == Cause.ADDRESS_DEPENDENCE and not round_id:
            await env.cycle(address_ready=SqPtr.encode(8))
        await env.issue_all()
        assert len({owner.uid for owner in env.model.owners.values() if owner.issued}) == 120
        await env.release_all()
    env.arm("LRQ-RECYCLE.many_rounds", all_uids)
    await env.idle(1)


async def test_strict_full_pool_is_not_unblocked_by_only_ready_bits(replay):
    env = replay
    for slot in range(120):
        req = env.request(Cause.ADDRESS_DEPENDENCE, rob=20 + slot, lq=slot, tag=slot + 1)
        req = replace(req, uop=replace(req.uop, strict=True, load_wait=True, store_set_hit=True))
        await env.cycle({slot % 3: req}, upper=SqPtr.encode(64))
    assert env.observed[P.p_lqFull]
    uids = [owner.uid for owner in env.model.owners.values()]
    env.arm(("LRQ-STORE.strict", "LRQ-STORE.strict_capacity"), uids)
    await env.idle(5, address_bits=(1 << 64) - 1)
    assert not any(env.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    await env.cycle(address_ready=SqPtr.encode(8))
    await env.issue_all()
    await env.release_all()
