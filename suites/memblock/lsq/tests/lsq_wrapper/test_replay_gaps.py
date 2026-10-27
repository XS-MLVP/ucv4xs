"""Scenarios derived from the remaining815 real Wrapper Replay DA rows."""
from dataclasses import replace

import pytest

from lsqverify.load_queue.types import Load
from lsqverify.lsq_wrapper.types import Address, Data
from lsqverify.raw.types import SqPtr
from lsqverify.replay.types import Cause, Refill, StoreWakeup, TlbHint
from lsqverify.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load
from .test_replay_population import drain_replays


def stores():
    return [StoreOwner(pos, RobPtr.encode(10), 0x20000 + pos * 16, 0xA020000 + pos * 16,
                       value=0x1122334455667700 + pos) for pos in range(8)]


async def no_replay(trace, count=5):
    for _ in range(count):
        await trace.cycle()
        assert not any(trace.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))


@pytest.mark.parametrize("ma_lane", range(3))
async def test_full_population_three_distinct_causes_keep_strict_and_other_owners(lsq, ma_lane):
    trace, old = MemoryOwners(lsq), stores()
    loads = []
    if ma_lane == 3:
        causes = [Cause.TLB_MISS, Cause.ADDRESS_DEPENDENCE, Cause.ADDRESS_DEPENDENCE]
    else:
        causes = [Cause.TLB_MISS, Cause.CACHE_MISS]
        causes.insert(ma_lane, Cause.ADDRESS_DEPENDENCE)
    for pos in range(120):
        load = cached_load(pos, 11 + pos, 8, 0x100000 + pos * 64, 0x80100000 + pos * 64)
        cause = causes[pos % 3]
        q = replace(load.execution, need_replay=True, causes=1 << cause, address_sq=SqPtr.encode(7), data_sq=SqPtr.encode(7),
                    tlb_id=pos % 16, mshr=pos % 16, handled=cause == Cause.CACHE_MISS,
                    uop=replace(load.execution.uop, strict=cause == Cause.ADDRESS_DEPENDENCE,
                                load_wait=cause == Cause.ADDRESS_DEPENDENCE, store_set_hit=cause == Cause.ADDRESS_DEPENDENCE,
                                wait_sq=SqPtr.encode(7)))
        loads.append(replace(load, execution=q))
    await trace.dispatch(old, loads)
    await trace.execute(loads)
    await no_replay(trace)
    # The actual valid STA wake and actual STA/STD name the same original
    # SQ7. Neither strict nor unrelated causes are cleared by disabled data.
    await trace.cycle(addresses=(Address(), old[7].address()), data=(old[7].data(), Data()),
                      address_wakeups=(StoreWakeup(True, SqPtr.encode(7)), StoreWakeup()))
    await trace.cycle(slow_tlb=TlbHint(True, 0, True))
    for identity in range(0, 16, 2):
        await trace.cycle(refills=(Refill(True, identity), Refill(True, identity + 1)))
    await trace.write_all()
    await drain_replays(trace, {state["uid"] for state in trace.loads})
    names = ["LSQ-REPLAY.strict", "LSQ-REPLAY.capacity"]
    if Cause.CACHE_MISS in causes:
        names.append("LSQ-REPLAY.refill")
    lsq.prove(*names, "LSQ-REPLAY.tlb")


async def test_three_lane_two_strict_waits_and_non_address_owner_keep_full_120_identities(lsq):
    await test_full_population_three_distinct_causes_keep_strict_and_other_owners(lsq, 3)


@pytest.mark.parametrize("strict", (False, True), ids=("bitmap-control", "strict-full-pool"))
async def test_full_population_real_ready_bitmap_does_not_replace_strict_execution_wakeup(lsq, strict):
    trace, old = MemoryOwners(lsq), stores()
    loads = []
    for pos in range(120):
        load = cached_load(pos, 11 + pos, 8, 0x100000 + pos * 64, 0x80100000 + pos * 64)
        q = replace(load.execution, need_replay=True, causes=1 << Cause.ADDRESS_DEPENDENCE,
                    address_sq=SqPtr.encode(7), data_sq=SqPtr.encode(7),
                    uop=replace(load.execution.uop, strict=strict, load_wait=True, store_set_hit=True, wait_sq=SqPtr.encode(7)))
        loads.append(replace(load, execution=q))
    await trace.dispatch(old, loads)
    for load in loads:
        await trace.execute([load])
    await no_replay(trace)
    await trace.write(7)
    if strict:
        lsq.reach("LSQ-REPLAY.strict")
        await no_replay(trace)
        await trace.cycle(addresses=(Address(), old[7].address()),
                          address_wakeups=(StoreWakeup(), StoreWakeup(True, SqPtr.encode(7))))
    await trace.write_all()
    await drain_replays(trace, {state["uid"] for state in trace.loads})
    lsq.prove("LSQ-REPLAY.capacity", "LSQ-REPLAY.sq_address")
    if strict:
        lsq.prove("LSQ-REPLAY.strict")


@pytest.mark.parametrize("lane", range(2))
async def test_real_std_issue_wakeup_history_precedes_matching_data_write_and_original_feedback(lsq, lane):
    trace = MemoryOwners(lsq)
    old = stores()[:2]
    load = cached_load(0, 11, 2, old[1].vaddr, old[1].paddr)
    load = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.FORWARD_FAILURE,
                                         data_sq=SqPtr.encode(1)))
    await trace.dispatch(old, [load])
    await trace.write(0, data=False)
    await trace.write(1, data=False)
    await trace.execute([load])
    await no_replay(trace)
    # An old nonmatching issue/written Store is not the missing SQ1 data.
    await trace.cycle(data=(old[0].data(), Data()), data_wakeups=(StoreWakeup(True, SqPtr.encode(0)), StoreWakeup()))
    await no_replay(trace)
    wake = tuple(StoreWakeup(True, SqPtr.encode(1)) if source == lane else StoreWakeup() for source in range(2))
    await trace.cycle(data_wakeups=wake)
    await trace.cycle(data=(Data(), old[1].data()))
    await trace.replay_complete(load)
    await trace.finish()
    lsq.prove("LSQ-REPLAY.sq_data", "LSQ-REPLAY.std_write")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("cause", (Cause.CACHE_REPLAY, Cause.WAY_PREDICTION))
async def test_cache_and_way_retry_each_s3_source_preserves_original_uid_to_feedback(lsq, lane, cause):
    trace = MemoryOwners(lsq)
    load = cached_load(0, 10, 0, 0x100000, 0x80100000)
    load = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << cause))
    await trace.dispatch(loads=[load])
    packet = [Load()] * 3
    packet[lane] = load
    await trace.cycle(loads=tuple(packet))
    await trace.replay_complete(load)
    await trace.finish()


@pytest.mark.parametrize("prefix", (2, 4))
async def test_actual_vlq_head_wins_in_other_replay_banks_not_only_bank_zero(lsq, prefix):
    trace = MemoryOwners(lsq)
    loads = [cached_load(pos, 10 + pos, 0, 0x100000 + pos * 64, 0x80100000 + pos * 64) for pos in range(120)]
    loads = [replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.BANK_CONFLICT)) for load in loads]
    await trace.dispatch(loads=loads)
    for load in loads[prefix:] + loads[:prefix]:
        await trace.execute([load])
    await trace.idle(5)
    slot, bank = 120 - prefix, (120 - prefix) % 3
    # An already selected request must hold while !ready. Head priority is
    # evaluated for the next available S1 selection, not by overwriting it.
    lsq.expect({f"io_replay_{bank}_valid": 1, f"io_replay_{bank}_bits_replayQueueIdx": bank},
               "original selected request holds through backpressure before new head selection")
    await trace.cycle(replay_ready=tuple(source == bank for source in range(3)))
    lsq.expect({f"io_replay_{bank}_valid": 1, f"io_replay_{bank}_bits_replayQueueIdx": slot,
                f"io_replay_{bank}_bits_uop_lqIdx_value": 0, f"io_replay_{bank}_bits_uop_lqIdx_flag": 0},
               "real VLQ head in bank1/2 defeats earlier Replay allocation age")
    await drain_replays(trace, {state["uid"] for state in trace.loads})
    lsq.prove("LSQ-REPLAY.head", "LSQ-REPLAY.capacity")
