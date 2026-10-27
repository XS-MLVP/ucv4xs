"""Real shared-S3 Replay obligations; no fake full/head/uncache-wake inputs."""
from dataclasses import replace

import pytest

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.types import Inputs, Load
from lsqverify.raw.types import SqPtr
from lsqverify.replay.types import Cause, L2Hint, Refill, StoreWakeup, TlbHint


def replay_load(load, cause, **fields):
    return replace(load, execution=replace(load.execution, need_replay=True, causes=1 << cause,
                                          address_sq=SqPtr.encode(7), data_sq=SqPtr.encode(7), tlb_id=15, mshr=15,
                                          handled=cause == Cause.CACHE_MISS, **fields))


async def blocked(actor, cycles=5, controls=None):
    for _ in range(cycles):
        await actor.step(controls or Inputs())
        assert not any(actor.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))


async def wait_issue(actor, uid, controls=None):
    base = replace(controls or Inputs(), replay_ready=(True,) * 3)
    for _ in range(40):
        await actor.step(base)
        if uid in actor.issued:
            return
    raise AssertionError(("original UID did not actually handshake Replay", uid))


@pytest.mark.parametrize("cause", range(1, 12))
async def test_supported_causes_shared_s3_dependency_and_real_feedback(lq, cause):
    # Cause0 is exercised through real bus/wakeup/bypass in test_uncache,
    # including all 16 IDs. It may not be driven as a fake internal wake.
    actor = LoadActor(lq)
    uids = await actor.dispatch(configure=lambda load: replay_load(load, cause))
    await actor.execute(uids, lanes=(cause % 3,))
    lq.reach("LQ-REPLAY.causes")
    if cause in (Cause.STORE_MULTI_MATCH, Cause.ADDRESS_DEPENDENCE, Cause.TLB_MISS, Cause.FORWARD_FAILURE, Cause.CACHE_MISS):
        await blocked(actor)
    pulse = Inputs()
    if cause == Cause.STORE_MULTI_MATCH:
        pulse = replace(pulse, dequeue=SqPtr.encode(10))
    elif cause == Cause.ADDRESS_DEPENDENCE:
        pulse = replace(pulse, address_bits=1 << 7)
    elif cause == Cause.TLB_MISS:
        pulse = replace(pulse, fast_tlb=TlbHint(True, 15))
    elif cause == Cause.FORWARD_FAILURE:
        pulse = replace(pulse, data_bits=1 << 7)
    elif cause == Cause.CACHE_MISS:
        pulse = replace(pulse, refills=(Refill(True, 15), Refill()))
    await actor.step(pulse)
    base = Inputs(dequeue=pulse.dequeue)
    await actor.drain(controls=base)
    actor.checked(("LQ-REPLAY.causes",), uids)


@pytest.mark.parametrize("lane", range(3))
async def test_all_120_replay_slots_each_s3_lane_two_generations(lq, lane):
    actor = LoadActor(lq)
    all_uids = []
    for generation in range(2):
        uids = []
        for _ in range(15):
            uids.extend(await actor.dispatch((1,) * 8))
        for uid in uids:
            owner = actor.owner(uid)
            request = owner.load.execution
            uop = replace(request.uop, operation=(uid % 4) << 1, fp_write=bool(uid & 2), integer_write=not bool(uid & 2),
                          vector_write=bool(uid & 1), v0_write=bool(uid & 4), store_set_hit=bool(uid & 8), load_wait=bool(uid & 16))
            owner.load = replace(owner.load, execution=replace(request, uop=uop, need_replay=True, causes=1 << Cause.BANK_CONFLICT,
                                 vaddr=request.vaddr + uid % 16, vector=bool(uid & 1), aligned_type=uid % 4, mask=(uid * 439) & 65535))
            await actor.execute([uid], lanes=(lane,))
        assert actor.tail - actor.head == 120
        lq.reach("LQ-CAPACITY.replay_pool", "LQ-REPLAY.metadata")
        await actor.drain()
        assert {actor.owner(uid).feedback_slot for uid in uids} == set(range(120))
        all_uids.extend(uids)
    actor.checked(("LQ-CAPACITY.replay_pool", "LQ-REPLAY.metadata"), all_uids)


async def test_same_owner_rereplay_updates_dependency_without_new_slot(lq):
    actor = LoadActor(lq)
    uids = await actor.dispatch(configure=lambda load: replay_load(load, Cause.BANK_CONFLICT))
    uid = uids[0]
    await actor.execute(uids)
    await wait_issue(actor, uid)
    slot = actor.issued[uid]
    owner = actor.owner(uid)
    owner.load = replay_load(replace(owner.load, execution=replace(owner.load.execution, vaddr=owner.load.execution.vaddr + 16)), Cause.TLB_MISS)
    await actor.feedback(uids, need_replay=True, causes=1 << Cause.TLB_MISS)
    lq.reach("LQ-REPLAY.update")
    await blocked(actor)
    assert uid not in actor.completed
    await actor.step(Inputs(fast_tlb=TlbHint(True, 15)))
    await wait_issue(actor, uid)
    assert actor.issued[uid] == slot
    await actor.feedback(uids)
    await actor.drain()
    actor.checked(("LQ-REPLAY.update",), uids)


@pytest.mark.parametrize("method", ("address_pointer", "address_bits", "address_wakeup", "data_pointer", "data_bits", "data_wakeup", "data_write", "sq_empty"))
async def test_real_sq_and_store_unit_dependency_paths(lq, method):
    actor = LoadActor(lq)
    address = method.startswith("address")
    cause = Cause.ADDRESS_DEPENDENCE if address else Cause.FORWARD_FAILURE
    uids = await actor.dispatch(configure=lambda load: replay_load(load, cause))
    if method == "data_write":
        await actor.execute(uids, controls=Inputs(data_writes=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
        base = Inputs()
    else:
        await actor.execute(uids)
        await blocked(actor)
        fields = {
            "address_pointer": dict(address_ready=SqPtr.encode(8)),
            "address_bits": dict(address_bits=1 << 7),
            "address_wakeup": dict(address_wakeups=(StoreWakeup(), StoreWakeup(True, SqPtr.encode(7)))),
            "data_pointer": dict(data_ready=SqPtr.encode(8)),
            "data_bits": dict(data_bits=1 << 7),
            "data_wakeup": dict(data_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())),
            "sq_empty": dict(sq_empty=True),
        }[method]
        base = Inputs(**fields)
        await actor.step(base)
    lq.reach("LQ-STORE.address" if address else "LQ-STORE.data")
    await actor.drain(controls=base)
    actor.checked(("LQ-STORE.address" if address else "LQ-STORE.data",), uids)


async def test_strict_address_wait_ignores_bitmap_until_real_matching_sta(lq):
    actor = LoadActor(lq)
    def configure(load):
        load = replay_load(load, Cause.ADDRESS_DEPENDENCE)
        return replace(load, execution=replace(load.execution, uop=replace(load.execution.uop, strict=True, load_wait=True, store_set_hit=True)))
    uids = await actor.dispatch(configure=configure)
    base = Inputs(address_bits=1 << 7)
    await actor.execute(uids, controls=base)
    await blocked(actor, controls=base)
    await actor.step(replace(base, address_wakeups=(StoreWakeup(True, SqPtr.encode(6)), StoreWakeup())))
    await blocked(actor, controls=base)
    lq.reach("LQ-STORE.strict")
    await actor.step(replace(base, address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
    await actor.drain(controls=base)
    actor.checked(("LQ-STORE.strict",), uids)


@pytest.mark.parametrize("lane", range(3))
async def test_disabled_s3_feedback_cannot_clear_live_strict_dependency(lq, lane):
    actor = LoadActor(lq)
    def configure(load):
        load = replay_load(load, Cause.ADDRESS_DEPENDENCE)
        return replace(load, execution=replace(load.execution, uop=replace(load.execution.uop, strict=True, load_wait=True, store_set_hit=True)))
    uids = await actor.dispatch(configure=configure)
    base = Inputs(address_bits=1 << 7)
    await actor.execute(uids, controls=base)
    await blocked(actor, controls=base)
    owner = actor.owner(uids[0])
    dirty = replace(owner.load, execution=replace(owner.load.execution, valid=False, replay_feedback=True, slot=0,
                    need_replay=False, causes=0, uop=replace(owner.load.execution.uop, strict=False)))
    loads = [Load()] * 3
    loads[lane] = dirty
    lq.reach("LQ-STORE.disabled")
    await actor.step(replace(base, loads=tuple(loads)))
    await blocked(actor, controls=base)
    await actor.step(replace(base, address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup())))
    await actor.drain(controls=base)
    actor.checked(("LQ-STORE.disabled",), uids)


@pytest.mark.parametrize("fast", (False, True))
async def test_all_tlb_ids_matching_mismatch_and_broadcast(lq, fast):
    actor = LoadActor(lq)
    all_uids = []
    for identity in range(16):
        def configure(load):
            load = replay_load(load, Cause.TLB_MISS)
            return replace(load, execution=replace(load.execution, tlb_id=identity))
        uids = await actor.dispatch(configure=configure)
        await actor.execute(uids)
        hint = TlbHint(True, identity ^ 1)
        await actor.step(Inputs(**{"fast_tlb" if fast else "slow_tlb": hint}))
        await blocked(actor)
        correct = TlbHint(True, identity if fast or identity % 2 == 0 else identity ^ 1, not fast and identity % 2 == 1)
        lq.reach("LQ-HINT.fast_tlb" if fast else "LQ-HINT.tlb")
        await actor.step(Inputs(**{"fast_tlb" if fast else "slow_tlb": correct}))
        await actor.drain()
        all_uids.extend(uids)
    actor.checked(("LQ-HINT.fast_tlb" if fast else "LQ-HINT.tlb",), all_uids)


@pytest.mark.parametrize("channel", (0, 1))
@pytest.mark.parametrize("unaligned", (False, True))
@pytest.mark.parametrize("distance", (1, 2, 3, 4))
async def test_real_refill_public_history_windows(lq, channel, unaligned, distance):
    actor = LoadActor(lq)
    uids = await actor.dispatch(configure=lambda load: replay_load(load, Cause.CACHE_MISS, unaligned_head=unaligned))
    refills = tuple(Refill(True, 15) if i == channel else Refill() for i in range(2))
    await actor.step(Inputs(refills=refills))
    for _ in range(distance - 1):
        await actor.step()
    await actor.execute(uids)
    for _ in range(4):
        await actor.step()
    visible = any(lq.observed[f"io_replay_{bank}_valid"] for bank in range(3))
    assert visible == (distance <= (3 if unaligned else 2))
    if not visible:
        await actor.step(Inputs(refills=(Refill(True, 3), Refill(True, 4))))
        await blocked(actor)
        await actor.step(Inputs(refills=refills))
    lq.reach("LQ-HINT.refill")
    await actor.drain()
    actor.checked(("LQ-HINT.refill",), uids)


@pytest.mark.parametrize("channel", (0, 1))
@pytest.mark.parametrize("last", (False, True))
@pytest.mark.parametrize("keyword", (False, True))
async def test_real_l2_hint_first_last_beat_and_wrong_mshr(lq, channel, last, keyword):
    actor = LoadActor(lq)
    uids = await actor.dispatch(configure=lambda load: replay_load(load, Cause.CACHE_MISS, last_beat=last))
    await actor.execute(uids)
    await actor.step(Inputs(l2_hints=(L2Hint(True, 1, keyword), L2Hint(True, 2, not keyword))))
    await blocked(actor)
    hints = tuple(L2Hint(True, 15, keyword) if i == channel else L2Hint() for i in range(2))
    lq.reach("LQ-HINT.l2")
    await actor.step(Inputs(l2_hints=hints))
    await actor.drain()
    actor.checked(("LQ-HINT.l2",), uids)
