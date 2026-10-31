"""Remaining public timing, recovery, valid-only and long-residence boundaries."""

from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr
from suites.memblock.lsq.replay.types import Cause, Enqueue, L2Hint, LqWakeup, Refill, StoreWakeup, TlbHint


@pytest.mark.parametrize("unaligned", (False, True))
@pytest.mark.parametrize("distance", (1, 2, 3))
async def test_slow_tlb_history_is_only_extended_for_s4_head(replay, unaligned, distance):
    env = replay
    req = env.request(Cause.TLB_MISS, unaligned_head=unaligned)
    await env.cycle(slow_tlb=TlbHint(True, req.tlb_id))
    hint_tick = env.last_tick
    await env.idle(distance - 1)
    await env.cycle({2: req})
    assert (env.last_tick - hint_tick) // 2 == distance
    uid = env.uid(req)
    await env.idle(4)
    assert bool(env.observed[P.p_replay_0_valid]) == (distance == 1 or unaligned and distance == 2)
    env.arm("LRQ-TLB.history", [uid])
    if not env.observed[P.p_replay_0_valid]:
        env.arm("LRQ-TLB.mismatch", [uid])
        await env.cycle(fast_tlb=TlbHint(True, req.tlb_id))
    await env.complete()


@pytest.mark.parametrize("unaligned", (False, True))
@pytest.mark.parametrize("distance", (1, 2, 3, 4))
@pytest.mark.parametrize("channel", (0, 1))
async def test_refill_history_windows_and_expired_negative(replay, unaligned, distance, channel):
    env = replay
    req = env.request(Cause.CACHE_MISS, unaligned_head=unaligned, mshr=15 if channel else 0)
    pulse = tuple(Refill(True, req.mshr) if i == channel else Refill() for i in range(2))
    await env.cycle(refills=pulse)
    hint_tick = env.last_tick
    await env.idle(distance - 1)
    await env.cycle({channel: req})
    assert (env.last_tick - hint_tick) // 2 == distance
    uid = env.uid(req)
    await env.idle(4)
    assert bool(env.observed[P.p_replay_0_valid]) == (distance <= (3 if unaligned else 2))
    env.arm(("LRQ-REFILL.history", "LRQ-REFILL.channels"), [uid])
    if not env.observed[P.p_replay_0_valid]:
        env.arm("LRQ-REFILL.mismatch", [uid])
        await env.cycle(refills=pulse)
    await env.complete()


@pytest.mark.parametrize("channel", (0, 1))
async def test_wrong_mshr_and_delayed_matching_refill(replay, channel):
    env = replay
    req = env.request(Cause.CACHE_MISS, mshr=15)
    await env.cycle({1: req})
    uid = env.uid(req)
    await env.cycle(refills=(Refill(True, 7), Refill(True, 8)), l2_hints=(L2Hint(True, 3, False), L2Hint(True, 4, True)))
    await env.idle(5)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(refills=tuple(Refill(True, 15) if i == channel else Refill() for i in range(2)))
    env.arm(("LRQ-REFILL.delayed", "LRQ-REFILL.mismatch", "LRQ-REFILL.channels"), [uid])
    await env.complete()


@pytest.mark.parametrize("nc", (False, True))
async def test_uncache_wakeup_flag_value_and_original_type(replay, nc):
    env = replay
    req = env.request(Cause.UNCACHE, lq=125, nc=nc)
    await env.cycle({2: req})
    uid = env.uid(req)
    await env.cycle(nc=LqWakeup(True, QueuePtr(not req.uop.lq.flag, req.uop.lq.value)))
    await env.cycle(mmio=LqWakeup(True, QueuePtr(req.uop.lq.flag, req.uop.lq.value + 1)))
    await env.idle(5)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(**{"nc" if nc else "mmio": LqWakeup(True, req.uop.lq)})
    env.arm(("LRQ-UNCACHE.mismatch", "LRQ-UNCACHE.nc" if nc else "LRQ-UNCACHE.mmio"), [uid])
    await env.complete()


@pytest.mark.parametrize("bank", range(3))
@pytest.mark.parametrize("mode", ("head", "near_head", "wrap"))
async def test_program_head_window_beats_insertion_age(replay, bank, mode):
    env = replay
    base = 119 if mode == "wrap" else 80
    target_lq = base if mode == "head" else base + 1
    reqs = [env.request(rob=40 + i, lq=base + 20 + i, tag=i + 1) for i in range(9)]
    target_slot = 6 + bank
    reqs[target_slot] = env.request(rob=20 if mode == "head" else 21, lq=target_lq, tag=99)
    # All other unfinished loads are PROGRAM-younger than ldWbPtr, despite
    # entering LRQ earlier. This is legal out-of-order execution, not a head
    # pointer artificially jumping past unfinished older records.
    for offset in range(0, 9, 3):
        await env.cycle({i: req for i, req in enumerate(reqs[offset:offset + 3])}, writeback=QueuePtr.encode(base))
    uids = [env.uid(req) for req in reqs]
    await env.idle(2)
    assert env.observed[P.io(f"replay_{bank}_bits_replayQueueIdx")] == bank
    await env.cycle(ready=tuple(i == bank for i in range(3)))
    assert env.observed[P.io(f"replay_{bank}_valid")]
    assert env.observed[P.io(f"replay_{bank}_bits_replayQueueIdx")] == target_slot
    env.arm("LRQ-ORDER." + mode, uids)
    env.arm("LRQ-HOLD.replace", uids)
    await env.issue_all()
    await env.release_all()


async def test_high_cause_group_overrides_older_low_group(replay):
    env = replay
    reqs = [env.request(lq=20 + i, rob=40 + i, tag=i + 1) for i in range(9)]
    reqs[6] = env.request(Cause.FORWARD_FAILURE, lq=26, rob=46, tag=33)
    for offset in range(0, 9, 3):
        await env.cycle(dict(enumerate(reqs[offset:offset + 3])))
    await env.cycle(data_bits=1 << 7)
    await env.cycle(ready=(True, False, False))
    assert env.observed[P.p_replay_0_bits_replayQueueIdx] == 6
    env.arm("LRQ-ORDER.priority", [env.uid(reqs[3]), env.uid(reqs[6])])
    await env.issue_all()
    await env.release_all()


async def test_rereplay_does_not_rejuvenate_original_insertion_age(replay):
    env = replay
    reqs = [env.request(Cause.TLB_MISS if i == 3 else Cause.BANK_CONFLICT, lq=20 + i, rob=40 + i, tag=i + 1) for i in range(6)]
    await env.cycle(dict(enumerate(reqs[:3])))
    await env.cycle(dict(enumerate(reqs[3:])))
    slot, uid = await env.issue(0)
    updated = replace(reqs[0], vaddr=reqs[0].vaddr + 16)
    await env.feedback(slot, lane=2, again=updated)
    await env.cycle(ready=(False,) * 3, fast_tlb=TlbHint(True, reqs[3].tlb_id))
    assert env.observed[P.p_replay_0_valid] and env.observed[P.p_replay_0_bits_replayQueueIdx] == 0
    env.arm("LRQ-ORDER.age", [uid, env.uid(reqs[3])])
    await env.issue_all()
    await env.release_all()


@pytest.mark.parametrize("cancel", (False, True))
async def test_cooldown_drains_already_fired_selection_and_can_recover(replay, cancel):
    env = replay
    for offset in range(0, 60, 3):
        await env.cycle({lane: env.request(lq=20 + offset + lane, rob=40 + offset + lane, tag=offset + lane + 1) for lane in range(3)})
    uids = [owner.uid for owner in env.model.owners.values()]
    saw_cold = False
    for _ in range(80):
        change = await env.cycle(ready=(True,) * 3)
        if any(count >= 12 for count in change["cooldown"]):
            saw_cold = True
            break
    assert saw_cold, "stimulus must reach a real consecutive-handshake cooldown"
    env.arm("LRQ-COOLDOWN.continuous", uids)
    if cancel:
        env.arm("LRQ-COOLDOWN.cancel", uids, reuse=True)
        await env.cycle(redirect=Redirect(True, RobPtr.encode(10), False))
        await env.idle(12, ready=(False,) * 3)
        assert not env.observed[P.p_replayAllocate]
        req = env.request(rob=20, lq=20)
        await env.cycle({2: req})
        await env.complete()
    else:
        await env.issue_all()
        await env.release_all()


async def test_nonconsecutive_handshakes_do_not_start_cooldown(replay):
    env = replay
    for offset in range(0, 45, 3):
        await env.cycle({lane: env.request(lq=20 + offset + lane, rob=40 + offset + lane) for lane in range(3)})
    uids = [owner.uid for owner in env.model.owners.values()]
    for _ in range(10):
        await env.cycle(ready=(True,) * 3)
        change = await env.cycle(ready=(False,) * 3)
        assert change["cooldown"] == [0, 0, 0]
    env.arm("LRQ-COOLDOWN.interrupted", uids)
    await env.issue_all()
    await env.release_all()


@pytest.mark.parametrize("phase", ("blocked", "selected", "issued"))
async def test_redirect_each_owner_phase_then_complete_new_uid(replay, phase):
    env = replay
    req = env.request(Cause.TLB_MISS if phase == "blocked" else Cause.BANK_CONFLICT)
    await env.cycle({1: req})
    uid = env.uid(req)
    await env.idle(4)
    if phase == "issued":
        await env.issue(0)
    env.arm("LRQ-FLUSH." + phase, [uid], reuse=True)
    await env.cycle(redirect=Redirect(True, req.uop.rob, True))
    await env.idle(8)
    assert not env.observed[P.p_replayAllocate]
    await env.cycle({2: env.request(rob=11, lq=21)})
    await env.complete()


@pytest.mark.parametrize("phase", ("blocked", "selected", "issued", "updated"))
async def test_active_reset_clears_pipeline_and_feedback_ownership(replay, phase):
    env = replay
    req = env.request(Cause.TLB_MISS if phase == "blocked" else Cause.BANK_CONFLICT)
    await env.cycle({1: req})
    await env.idle(3)
    if phase in ("issued", "updated"):
        await env.issue(0)
    if phase == "updated":
        await env.feedback(0, again=env.request(Cause.TLB_MISS))
    await env.reset()
    await env.cycle({2: env.request(rob=20, lq=30)})
    await env.complete()


@pytest.mark.parametrize("case", range(6))
async def test_redirect_slot_age_former_latter_and_rob_wrap(replay, case):
    env = replay
    cases = ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), False, False),
             (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False, True),
             (RobPtr.encode(10), RobPtr.encode(10), False, False),
             (RobPtr.encode(10), RobPtr.encode(10), True, True),
             (RobPtr.encode(160), RobPtr.encode(159), False, True),
             (RobPtr.encode(159), RobPtr.encode(160), False, False))
    own, cutoff, self_flush, canceled = cases[case]
    req = env.request(Cause.TLB_MISS)
    req = replace(req, uop=replace(req.uop, rob=own))
    await env.cycle({2: req})
    uid = env.uid(req)
    await env.cycle(redirect=Redirect(True, cutoff, self_flush))
    if canceled:
        assert not env.observed[P.p_replayAllocate]
        env.arm("LRQ-FLUSH.age", [uid], reuse=True)
        await env.idle(6)
        await env.cycle({0: env.request()})
    else:
        assert env.observed[P.p_replayAllocate]
        env.arm("LRQ-FLUSH.age", [uid])
        await env.cycle(fast_tlb=TlbHint(True, req.tlb_id))
    await env.complete()


async def test_normal_feedback_and_redirect_same_slot_do_not_double_return(replay):
    env = replay
    req = env.request()
    await env.cycle({0: req})
    slot, uid = await env.issue()
    done = replace(req, replay_feedback=True, slot=slot, need_replay=False)
    await env.cycle({2: done}, redirect=Redirect(True, req.uop.rob, True))
    assert not env.observed[P.p_replayAllocate]
    env.arm("LRQ-FLUSH.overlap", [uid])
    await env.idle(8)
    await env.cycle({1: env.request(rob=11, lq=21)})
    await env.complete()


@pytest.mark.parametrize("cancel", (False, True))
async def test_no_need_or_already_redirected_input_does_not_allocate(replay, cancel):
    env = replay
    req = env.request()
    if cancel:
        await env.cycle({2: req}, redirect=Redirect(True, req.uop.rob, True))
    else:
        await env.cycle({1: replace(req, need_replay=False, causes=0x1FFF)})
    await env.idle(5)
    assert not env.observed[P.p_replayAllocate]
    new = env.request(rob=11, lq=21)
    await env.cycle({2: new})
    env.arm("LRQ-ADMIT.redirect" if cancel else "LRQ-ADMIT.no_need", [env.uid(new)])
    await env.complete()


async def test_disabled_feedback_payload_does_not_update_non_strict_owner(replay):
    env = replay
    req = env.request(Cause.TLB_MISS)
    await env.cycle({0: req})
    uid = env.uid(req)
    dirty = replace(env.request(Cause.CACHE_MISS, tag=99), valid=False, replay_feedback=True, slot=0, need_replay=False, causes=0x1FFF)
    await env.idle(6)
    await env.cycle({2: dirty}, refills=(Refill(True, 15), Refill(True, 14)))
    await env.idle(4)
    assert not env.observed[P.p_replay_0_valid]
    env.arm("LRQ-IDLE.disabled", [uid])
    await env.cycle(fast_tlb=TlbHint(True, req.tlb_id))
    await env.complete()


@pytest.mark.parametrize("lane", range(3))
async def test_disabled_feedback_cannot_clear_strict_dependency(replay, lane):
    env = replay
    req = env.request(Cause.ADDRESS_DEPENDENCE)
    req = replace(req, uop=replace(req.uop, strict=True, load_wait=True, store_set_hit=True))
    await env.cycle({0: req}, address_bits=1 << 7, upper=SqPtr.encode(64))
    uid = env.uid(req)
    await env.idle(4)
    assert not env.observed[P.p_replay_0_valid]
    dirty = replace(req, valid=False, replay_feedback=True, slot=0, need_replay=False, causes=0,
                    uop=replace(req.uop, strict=False))
    env.arm("LRQ-STORE.strict_valid_only", [uid])
    await env.cycle({lane: dirty})
    await env.idle(5)
    assert not env.observed[P.p_replay_0_valid]
    await env.cycle(address_ready=SqPtr.encode(8))
    await env.complete()


@pytest.mark.parametrize("former_change", (False, True))
async def test_special_threshold_normal_young_wait_and_marked_request(replay, former_change):
    env = replay
    req = env.request(Cause.TLB_MISS, special_eligible=True)
    await env.cycle(head=req.uop.rob)
    await env.cycle({0: req})
    uid = env.uid(req)
    await env.idle(2046)
    assert not env.observed[P.p_specialMode]
    await env.cycle()
    assert not env.observed[P.p_specialMode]
    await env.cycle()
    assert env.observed[P.p_specialMode]
    normal = env.request(Cause.TLB_MISS, rob=12, lq=22)
    await env.cycle({1: normal})
    await env.idle(4)
    assert not env.observed[P.p_replay_1_valid]
    marked = env.request(Cause.TLB_MISS, rob=11, lq=21, special_request=True)
    await env.cycle({2: marked})
    marked_uid = env.uid(marked)
    env.arm("LRQ-SPECIAL.request", [marked_uid])
    await env.complete(2)
    new_head = replace(req.uop.rob, former=not req.uop.rob.former) if former_change else RobPtr.encode(11)
    await env.cycle(head=new_head)
    assert not env.observed[P.p_specialMode]
    env.arm(("LRQ-SPECIAL.threshold", "LRQ-SPECIAL.head_moves"), [uid, env.uid(normal)])
    await env.cycle(slow_tlb=TlbHint(True, 0, True))
    await env.issue_all()
    await env.release_all()


@pytest.mark.parametrize("cancel", (False, True))
async def test_noneligible_or_canceled_input_does_not_start_special_window(replay, cancel):
    env = replay
    req = env.request(Cause.TLB_MISS, special_eligible=cancel)
    await env.cycle(head=req.uop.rob)
    await env.cycle({0: req}, redirect=Redirect(True, req.uop.rob, True) if cancel else Redirect())
    await env.idle(2050)
    assert not env.observed[P.p_specialMode]
    if not cancel:
        await env.cycle(fast_tlb=TlbHint(True, req.tlb_id))
        uid = env.uid(req)
        env.arm("LRQ-SPECIAL.not_eligible", [uid])
        await env.complete()
    else:
        new = env.request()
        await env.cycle({1: new})
        env.arm("LRQ-SPECIAL.not_eligible", [env.uid(new)])
        await env.complete()


async def test_cause_feedback_does_not_restart_existing_special_window(replay):
    env = replay
    req = env.request(special_eligible=True)
    await env.cycle(head=req.uop.rob)
    await env.cycle({0: req})
    trigger_tick = env.last_tick
    slot, uid = await env.issue()
    again = replace(req, causes=1 << Cause.TLB_MISS, special_eligible=False)
    await env.feedback(slot, again=again)
    elapsed = (env.last_tick - trigger_tick) // 2
    await env.idle(2047 - elapsed)
    assert not env.observed[P.p_specialMode]
    await env.cycle()
    assert env.observed[P.p_specialMode]
    env.arm("LRQ-SPECIAL.rereplay", [uid])
    await env.cycle(fast_tlb=TlbHint(True, again.tlb_id))
    await env.complete(slot)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_concurrent_replay_feedback_and_dependencies(replay, seed):
    env = replay
    rng = random.Random(seed)
    for cycle in range(700):
        reqs = {}
        issued = [owner for owner in env.model.owners.values() if owner.issued]
        rng.shuffle(issued)
        for lane, owner in enumerate(issued[:rng.randrange(4)]):
            again = rng.random() < 0.3
            req = owner.request
            if again:
                req = replace(req, causes=1 << rng.randrange(12), tlb_id=rng.randrange(16), mshr=rng.randrange(16), last_beat=bool(rng.randrange(2)), handled=True)
            reqs[lane] = replace(req, replay_feedback=True, slot=owner.slot, need_replay=again)
        live_lq = {owner.request.uop.lq for owner in env.model.owners.values()}
        available_lq = [QueuePtr.encode(index) for index in range(10, 110) if QueuePtr.encode(index) not in live_lq]
        rng.shuffle(available_lq)
        count = min(env.model.pool.offered, len(available_lq), rng.randrange(4))
        for lane in range(3):
            if lane in reqs or count == 0:
                continue
            ptr = available_lq.pop()
            req = env.request(rng.randrange(12), rob=20 + ptr.value, lq=ptr.value, sq=rng.randrange(32), tag=cycle * 3 + lane + 1,
                              mshr=rng.randrange(16), tlb_id=rng.randrange(16), last_beat=bool(rng.randrange(2)),
                              vector=bool(rng.randrange(2)), aligned_type=rng.randrange(8), mask=rng.randrange(1 << 16))
            reqs[lane] = req
            count -= 1
        owners = list(env.model.owners.values())
        rng.shuffle(owners)
        mshr = [rng.randrange(16) for _ in range(2)]
        if owners:
            mshr[0] = owners[0].mshr
        l2 = (L2Hint(rng.random() < 0.3, mshr[0], bool(rng.randrange(2))), L2Hint(rng.random() < 0.3 and mshr[1] != mshr[0], mshr[1], bool(rng.randrange(2))))
        addr = list(dict.fromkeys(owner.request.address_sq for owner in owners))
        data = list(dict.fromkeys(owner.request.data_sq for owner in owners))
        sa = tuple(StoreWakeup(rng.random() < 0.5, addr[i]) if len(addr) > i else StoreWakeup() for i in range(2))
        sd = tuple(StoreWakeup(rng.random() < 0.5, data[i]) if len(data) > i else StoreWakeup() for i in range(2))
        nc = LqWakeup(rng.random() < 0.5, owners[0].request.uop.lq) if owners else LqWakeup()
        mmio = LqWakeup(rng.random() < 0.5, owners[1].request.uop.lq) if len(owners) > 1 else LqWakeup()
        await env.cycle(reqs, ready=tuple(rng.random() < 0.7 for _ in range(3)), upper=SqPtr.encode(64),
                        rar_full=bool(rng.randrange(2)), raw_full=bool(rng.randrange(2)), address_bits=rng.getrandbits(64), data_bits=rng.getrandbits(64),
                        address_wakeups=sa, data_wakeups=sd, data_writes=sd, nc=nc, mmio=mmio,
                        refills=(Refill(rng.random() < 0.4, mshr[0]), Refill(rng.random() < 0.4, mshr[1])),
                        l2_hints=l2, slow_tlb=TlbHint(rng.random() < 0.5, rng.randrange(16), rng.random() < 0.1),
                        fast_tlb=TlbHint(rng.random() < 0.4, rng.randrange(16)))
    for step in range(300):
        if all(owner.issued for owner in env.model.owners.values()):
            break
        blocked_uncache = [owner for owner in env.model.owners.values() if owner.request.causes == 1 << Cause.UNCACHE and owner.blocked]
        wake = [LqWakeup(True, owner.request.uop.lq) for owner in blocked_uncache[:2]]
        await env.cycle(ready=(True,) * 3, address_ready=SqPtr.encode(64), data_ready=SqPtr.encode(64), dequeue=SqPtr.encode(64),
                        sq_empty=True, rar_full=False, raw_full=False, slow_tlb=TlbHint(True, 0, True),
                        refills=(Refill(True, step % 16), Refill(True, (step + 8) % 16)),
                        nc=wake[0] if wake else LqWakeup(), mmio=wake[1] if len(wake) > 1 else LqWakeup())
    else:
        raise AssertionError("legal random replay did not drain with all dependencies satisfied")
    await env.release_all()
