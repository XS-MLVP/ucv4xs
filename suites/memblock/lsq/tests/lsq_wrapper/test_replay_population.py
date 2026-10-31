"""Full real Replay populations; SQ dependencies are produced by REAL stores."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.lsq_wrapper.types import Address
from suites.memblock.lsq.replay.types import Cause, Refill, StoreWakeup, TlbHint
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load


async def drain_replays(trace, uids):
    for _ in range(1000):
        feedback = []
        for state in trace.loads:
            if state["uid"] not in uids or state["sent"] or "grant" not in state:
                continue
            load = state["load"]
            feedback.append(replace(load, execution=replace(load.execution, replay_feedback=True, slot=state["grant"], need_replay=False, causes=0)))
            if len(feedback) == 3:
                break
        await trace.cycle(loads=tuple(feedback) + (Load(),) * (3 - len(feedback)), replay_ready=(True, True, True))
        if all(state["completed"] for state in trace.loads if state["uid"] in uids):
            assert {state["grant"] for state in trace.loads if state["uid"] in uids} == set(range(120))
            await trace.finish()
            return
    raise AssertionError("actual full Replay population did not fairly finish original grants/slot feedback/VLQ credits")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("cause", (Cause.ADDRESS_DEPENDENCE, Cause.TLB_MISS, Cause.CACHE_MISS), ids=("actual-sq-address", "tlb", "mshr"))
async def test_full_120_replay_slots_from_each_s3_input_keep_dependency_and_uid(lsq, lane, cause):
    trace = MemoryOwners(lsq)
    stores = ([StoreOwner(pos, RobPtr.encode(10), 0x20000 + pos * 16, 0xA020000 + pos * 16,
                          value=0x1122334455667700 + pos) for pos in range(8)] if cause == Cause.ADDRESS_DEPENDENCE else [])
    first_rob, sq_end = (11, 8) if stores else (10, 0)
    loads = []
    for pos in range(120):
        load = cached_load(pos, first_rob + pos, sq_end, 0x100000 + pos * 64, 0x80100000 + pos * 64)
        q = replace(load.execution, need_replay=True, causes=1 << cause, address_sq=SqPtr.encode(7 if stores else 0),
                    data_sq=SqPtr.encode(7 if stores else 0), tlb_id=pos % 16, mshr=pos % 16,
                    handled=cause == Cause.CACHE_MISS, last_beat=bool(pos & 1))
        loads.append(replace(load, execution=q))
    await trace.dispatch(stores, loads)
    for load in loads:
        packet = [Load()] * 3
        packet[lane] = load
        await trace.cycle(loads=tuple(packet))
    lsq.reach("LSQ-REPLAY.capacity")
    for _ in range(5):
        await trace.cycle()
        assert not any(lsq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    if stores:
        # Real Store writes/registered ready vectors/pointer release SQ7.
        # No external address_ready/data_ready/full/empty feedback exists.
        await trace.write_all()
    elif cause == Cause.TLB_MISS:
        await trace.cycle(slow_tlb=TlbHint(True, 0, True))
    else:
        for identity in range(0, 16, 2):
            await trace.cycle(refills=(Refill(True, identity), Refill(True, identity + 1)))
    selected = {state["uid"] for state in trace.loads}
    await drain_replays(trace, selected)
    lsq.prove("LSQ-REPLAY.capacity", "LSQ-ALLOC.lq_capacity",
              "LSQ-REPLAY.sq_address" if stores else "LSQ-REPLAY.tlb" if cause == Cause.TLB_MISS else "LSQ-REPLAY.refill")


async def test_real_vlq_head_is_last_into_replay_but_wins_head_near_candidates(lsq):
    trace = MemoryOwners(lsq)
    loads = [cached_load(pos, 10 + pos, 0, 0x100000 + pos * 64, 0x80100000 + pos * 64) for pos in range(120)]
    loads = [replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.BANK_CONFLICT)) for load in loads]
    await trace.dispatch(loads=loads)
    for load in loads[3:] + loads[:3]:
        await trace.execute([load])
    await trace.idle(3)
    await trace.cycle(replay_ready=(True, True, True))
    lsq.expect({P.io(f"replay_{bank}_bits_replayQueueIdx"): 117 + bank for bank in range(3)},
               "actual VLQ head/head-near owners beat older Replay allocation age")
    await drain_replays(trace, {state["uid"] for state in trace.loads})
    lsq.prove("LSQ-REPLAY.head", "LSQ-REPLAY.capacity")


async def test_each_dispatch_source_owns_real_120_multi_flow_loads_across_lq_wraps(lsq):
    trace = MemoryOwners(lsq)
    position, rob = 0, 10
    for lane in range(8):
        wave = []
        for count in (16,) * 7 + (8,):
            loads = [cached_load(pos, rob, 0, 0x100000 + pos * 64, 0x80100000 + pos * 64) for pos in range(position, position + count)]
            # A retained multi-element ROB interval, with vector result class
            # consistent across all its externally completed element flows.
            loads = [replace(load, execution=replace(load.execution, vector=True,
                     uop=replace(load.execution.uop, integer_write=False, vector_write=True))) for load in loads]
            await trace.dispatch(loads=loads, load_lane=lane)
            wave += loads
            position += count
            rob += 1
        await trace.idle(2)
        assert not lsq.observed[P.p_lqEmpty]
        await trace.finish()
        assert all(state["completed"] for state in trace.loads)
    assert len(trace.loads) == position == 960
    lsq.prove("LSQ-ALLOC.all_lanes", "LSQ-ALLOC.multi_flow", "LSQ-ALLOC.lq_capacity", "LSQ-ALLOC.lq_wrap")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("dirty", (False, True), ids=("valid-wakeup-control", "disabled-feedback"))
async def test_actual_sq_bitmap_cannot_clear_strict_from_disabled_feedback(lsq, lane, dirty):
    trace = MemoryOwners(lsq)
    stores = [StoreOwner(pos, RobPtr.encode(10 + pos), 0x20000 + pos * 16, 0xA020000 + pos * 16,
                         value=0x1122334455667700 + pos) for pos in range(2)]
    load = cached_load(0, 12, 2, 0x100000, 0x80100000)
    load = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.ADDRESS_DEPENDENCE,
                   address_sq=SqPtr.encode(1), data_sq=SqPtr.encode(1),
                   uop=replace(load.execution.uop, strict=True, load_wait=True, store_set_hit=True, wait_sq=SqPtr.encode(1))))
    await trace.dispatch(stores, [load])
    # Slot1 is actually ready, but the real address pointer remains at the
    # hole in slot0. The remembered strict wait requires a matching event,
    # not only a true physical bitmap. There is no external SQ feedback pin.
    await trace.write(1)
    await trace.idle(3)
    lsq.expect({P.p_issuePtrExt_value: 0}, "real earlier STA hole prevents the ready pointer from passing strict dependency")
    await trace.execute([load])
    for _ in range(5):
        await trace.cycle()
        assert not any(lsq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    lsq.reach("LSQ-REPLAY.strict")
    if dirty:
        disabled = replace(load, execution=replace(load.execution, valid=False, replay_feedback=True, slot=0,
                           need_replay=False, causes=0, uop=replace(load.execution.uop, strict=False)))
        packet = [Load()] * 3
        packet[lane] = disabled
        lsq.reach("LSQ-REPLAY.disabled")
        await trace.cycle(loads=tuple(packet))
        for _ in range(5):
            await trace.cycle()
            assert not any(lsq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
    # A real matching Store execution wake, with a same-owner STA update,
    # then actual old-hole completion permits ordinary final Store writeout.
    await trace.cycle(address_wakeups=(StoreWakeup(True, SqPtr.encode(1)), StoreWakeup()),
                      addresses=(Address(), stores[1].address()))
    await trace.write_all()
    await trace.replay_complete(load)
    await trace.finish()
    lsq.prove("LSQ-REPLAY.strict")
    if dirty:
        lsq.prove("LSQ-REPLAY.disabled")


@pytest.mark.parametrize("eligible,former_change", ((False, False), (True, False), (True, True)))
async def test_special_mode_2048_cycles_and_legal_next_head_after_original_feedback(lsq, eligible, former_change):
    trace = MemoryOwners(lsq)
    load = cached_load(0, 10, 0, 0x100000, 0x80100000)
    load = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.TLB_MISS,
                                         tlb_id=15, special_eligible=eligible))
    await trace.dispatch(loads=[load])
    trace.base = replace(trace.base, pending=load.execution.uop.rob, pending_next=load.execution.uop.rob)
    # A head movement has priority over the trigger at that edge. Establish
    # the real current head before its S3 replay starts the wait window.
    await trace.cycle()
    await trace.execute([load])
    trigger = lsq.last_tick
    for _ in range(2047):
        await trace.cycle()
        assert not lsq.observed[P.p_specialMode]
    await trace.cycle()
    assert (lsq.last_tick - trigger) // 2 == 2048 and bool(lsq.observed[P.p_specialMode]) == eligible
    await trace.cycle(fast_tlb=TlbHint(True, 15))
    await trace.replay_complete(load)
    # Only after original Load execution really completes may ROB's next
    # head move. No fake retirement over an unfinished TLB-miss Load.
    next_head = replace(load.execution.uop.rob, former=False) if former_change else RobPtr.encode(11)
    trace.base = replace(trace.base, pending_next=next_head)
    await trace.cycle()
    lsq.expect({P.p_specialMode: 0}, "special mode clears for the actual next head after normal original feedback")
    await trace.finish()
    lsq.prove("LSQ-REPLAY.special")
