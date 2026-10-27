"""Second line-gap expansion and necessary-condition controls for strict."""
from dataclasses import replace

import pytest

from lsqverify.raw.types import FtqPtr, SqPtr
from lsqverify.vlq.types import QueuePtr, Redirect, RobPtr
from lsqverify.replay.types import Cause, Enqueue, LqWakeup, StoreWakeup, TlbHint


async def fill_tlb_pool(env, *, sentinel_ids=0):
    for offset in range(0, 120, 3):
        reqs = {}
        for lane in range(3):
            index = offset + lane
            reqs[lane] = env.request(Cause.TLB_MISS, rob=20 + index, lq=index, tag=index + 1,
                                     tlb_id=index if index < sentinel_ids else 15, mshr=index % 16)
        await env.cycle(reqs)
    assert env.observed["io_lqFull"] and len(env.model.owners) == 120


@pytest.mark.parametrize("control", ("not_feedback", "different_slot", "address_not_ready", "ordinary_non_strict"))
async def test_valid_only_strict_necessary_condition_controls(replay, control):
    env = replay
    strict = control != "ordinary_non_strict"
    bits = 0 if control == "address_not_ready" else 1 << 7
    req = env.request(Cause.ADDRESS_DEPENDENCE)
    req = replace(req, uop=replace(req.uop, strict=strict, load_wait=True, store_set_hit=True))
    await env.cycle({0: req}, address_bits=bits, upper=SqPtr.encode(64))
    uid = env.uid(req)
    await env.idle(4)
    assert bool(env.observed["io_replay_0_valid"]) == (not strict and bool(bits))
    dirty = replace(req, valid=False, replay_feedback=control != "not_feedback", slot=1 if control == "different_slot" else 0,
                    need_replay=False, causes=0, uop=replace(req.uop, strict=False))
    await env.cycle({2: dirty})
    await env.idle(5)
    assert bool(env.observed["io_replay_0_valid"]) == (not strict and bool(bits))
    env.arm("LRQ-IDLE.disabled", [uid])
    await env.cycle(address_ready=SqPtr.encode(8))
    await env.complete()


async def test_three_feedback_ports_update_every_slot_strict_and_tlb_tags(replay):
    env = replay
    await fill_tlb_pool(env)
    uids = [owner.uid for owner in env.model.owners.values()]
    await env.cycle(slow_tlb=TlbHint(True, 0, True))
    await env.issue_all()
    for cause in (Cause.ADDRESS_DEPENDENCE, Cause.TLB_MISS):
        for rotation in range(3):
            await env.idle(3, ready=(False,) * 3)
            for offset in range(0, 120, 3):
                reqs = {}
                for index in range(3):
                    slot = offset + index
                    owner = env.model.owners[slot]
                    req = replace(owner.request, replay_feedback=True, slot=slot, need_replay=True, causes=1 << cause,
                                  tlb_id=(slot + rotation) % 16, uop=replace(owner.request.uop, strict=True, load_wait=True, store_set_hit=True))
                    reqs[(index + rotation) % 3] = req
                await env.cycle(reqs)
            assert env.model.sequence == 120
            if cause == Cause.ADDRESS_DEPENDENCE:
                # Speculative producer wakeups can recur while actual address
                # readiness remains unchanged; do not rewind a monotonic pointer.
                await env.cycle(address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup()))
            else:
                await env.cycle(slow_tlb=TlbHint(True, 0, True))
            await env.issue_all()
    env.arm(("LRQ-OWNER.rereplay", "LRQ-OWNER.changed_cause", "LRQ-BANK.all_slots", "LRQ-PERF.events"), uids)
    await env.release_all()


async def test_full_width_replay_metadata_and_pointer_identity_reuses_slot(replay):
    """Preserve legal high-width metadata across two released transactions.

    The first generation exercises the public boundary values that are legal
    for this 120-entry/160-ROB configuration.  After a real output handshake
    and feedback release, a new transaction receives the low boundary values.
    This test does not prove that both transactions use the same physical
    slot; test_pool_payload.py checks full-pool reuse using public slot IDs.
    The independent ReplayModel checks the complete public
    payload on both generations; no DUT register or slot memory is used as an
    oracle.
    """
    env = replay
    high = env.request(
        Cause.BANK_CONFLICT,
        rob=159,
        lq=119,
        sq=255,
        tag=127,
        vaddr=(1 << 50) - 16,
        mask=0xFFFF,
        nc=True,
        vector=True,
        aligned_type=7,
        mshr=15,
        tlb_id=15,
        unaligned_head=True,
    )
    high = replace(
        high,
        uop=replace(
            high.uop,
            rob=RobPtr.encode(159, former=False),
            lq=QueuePtr.encode(119),
            sq=SqPtr.encode(255),
            ftq=FtqPtr(True, 63),
            offset=31,
            rvc=True,
            checkpoint=(1 << 64) - 1,
            operation=6,
            integer_write=False,
            fp_write=True,
            vector_write=True,
            v0_write=True,
            destination=255,
            store_set_hit=True,
            wait_sq=SqPtr.encode(191),
            load_wait=True,
            strict=True,
            exceptions=sum(1 << bit for bit in (23, 19, 15, 7, 6)),
        ),
        data_sq=SqPtr.encode(255),
        address_sq=SqPtr.encode(255),
    )
    await env.cycle({1: high})
    high_uid = env.uid(high)
    env.arm(("LRQ-PAYLOAD.metadata", "LRQ-PAYLOAD.vector", "LRQ-OWNER.wait_feedback"), [high_uid])
    await env.idle(6)
    assert any(
        env.observed[f"io_replay_{bank}_valid"]
        and env.observed[f"io_replay_{bank}_bits_uop_perfDebugInfo_runahead_checkpoint_id"] == (1 << 64) - 1
        for bank in range(3)
    )
    await env.complete()

    low = env.request(Cause.BANK_CONFLICT, rob=10, lq=20, sq=0, tag=0, vaddr=0, mask=1)
    low = replace(
        low,
        uop=replace(
            low.uop,
            rob=RobPtr.encode(10, former=True),
            lq=QueuePtr.encode(20),
            sq=SqPtr.encode(0),
            ftq=FtqPtr(False, 0),
            offset=0,
            rvc=False,
            checkpoint=0,
            operation=6,
            integer_write=True,
            fp_write=False,
            vector_write=False,
            v0_write=False,
            destination=0,
            store_set_hit=False,
            wait_sq=SqPtr.encode(0),
            load_wait=False,
            strict=False,
            exceptions=0,
        ),
        data_sq=SqPtr.encode(0),
        address_sq=SqPtr.encode(0),
    )
    await env.cycle({2: low})
    low_uid = env.uid(low)
    env.arm(("LRQ-PAYLOAD.metadata", "LRQ-PAYLOAD.scalar"), [low_uid])
    await env.complete()


@pytest.mark.parametrize("padding", (0, 1, 2, 3))
async def test_four_return_channels_at_each_fifo_tail_alignment(replay, padding):
    env = replay
    await fill_tlb_pool(env, sentinel_ids=padding)
    canceled_uids = []
    for slot in range(padding):
        await env.cycle(fast_tlb=TlbHint(True, slot))
        await env.complete(slot, lane=(slot + 1) % 3)
    await env.idle(5)
    assert len(env.model.pool.available) == padding
    canceled_uids = [owner.uid for owner in env.model.owners.values()]
    env.arm("LRQ-FLUSH.blocked", canceled_uids, reuse=True)
    await env.cycle(redirect=Redirect(True, RobPtr.encode(10), False))
    await env.idle(50)
    assert not env.observed["io_replayAllocate"]
    for offset in range(0, 120, 3):
        await env.cycle({lane: env.request(rob=20 + offset + lane, lq=offset + lane, tag=offset + lane + 129)
                         for lane in range(3)})
    uids = [owner.uid for owner in env.model.owners.values()]
    env.arm(("LRQ-RECYCLE.full", "LRQ-RECYCLE.banks", "LRQ-RECYCLE.many_rounds"), uids)
    await env.issue_all()
    await env.release_all()


@pytest.mark.parametrize("base", (0, 119))
async def test_each_slot_selected_in_program_head_window_after_real_completion(replay, base):
    env = replay
    await env.cycle(writeback=QueuePtr.encode(base))
    for offset in range(0, 120, 3):
        await env.cycle({lane: env.request(Cause.UNCACHE, rob=20 + offset + lane, lq=base + offset + lane,
                                            tag=offset + lane + 1, nc=bool(lane % 2)) for lane in range(3)})
    uids = [owner.uid for owner in env.model.owners.values()]
    env.arm(("LRQ-ORDER.head", "LRQ-ORDER.near_head", "LRQ-ORDER.wrap"), uids)
    for offset in range(0, 120, 3):
        # No earlier LQ remains unfinished when the writeback pointer moves.
        assert all(owner.request.uop.lq != QueuePtr.encode(base + i) for owner in env.model.owners.values() for i in range(offset))
        await env.cycle(writeback=QueuePtr.encode(base + offset), ready=(False,) * 3,
                        mmio=LqWakeup(True, QueuePtr.encode(base + offset)), nc=LqWakeup(True, QueuePtr.encode(base + offset + 1)))
        await env.cycle(mmio=LqWakeup(True, QueuePtr.encode(base + offset + 2)))
        await env.idle(3)
        for bank in range(3):
            assert env.observed[f"io_replay_{bank}_valid"]
            assert env.observed[f"io_replay_{bank}_bits_replayQueueIdx"] == offset + bank
        change = await env.cycle(ready=(True,) * 3)
        assert len(change["fired"]) == 3
        feedback = {bank: replace(env.model.owners[offset + bank].request, replay_feedback=True,
                                  slot=offset + bank, need_replay=False) for bank in range(3)}
        change = await env.cycle(feedback, ready=(False,) * 3)
        assert len(change["completed"]) == 3
    await env.idle(8)
    assert not env.model.owners and not env.observed["io_replayAllocate"]
