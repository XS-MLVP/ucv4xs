"""Cases derived from all 4405 first-pass line gaps and missing semantic scenarios."""
import random

import pytest

from suites.memblock.lsq.vlq.types import Dispatch, QueuePtr, Redirect, RobPtr, Writeback


async def fill_on_one_lane(env, size, lane):
    remaining = size
    allocated = []
    while remaining:
        count = min(env.spec["max_flows_per_request"], remaining)
        change = await env.cycle(dispatch=env.build_dispatch((count,), lanes=(lane,)))
        allocated.extend(item.position for item in change.allocated)
        remaining -= count
    return tuple(allocated)


async def test_all_dispatch_lanes_preserve_complete_ring_and_rob_labels(vlq):
    env = vlq
    for lane in range(env.spec["dispatch_width"]):
        start = env.model.tail
        assert await fill_on_one_lane(env, 120, lane) == tuple(range(start, start + 120))
        await env.idle(4)
        assert env.observed.head == QueuePtr.encode(start)
        assert await env.complete_and_drain(newest_first=bool(lane % 2)) == tuple(range(start, start + 120))

        # Labels cannot be read back directly. For every source lane, include
        # ROB flag and former/latter differences, then observe their effects
        # through cancellation counts, a recovery pointer and survivor release.
        base = (env.next_rob_entry // 160) * 160 + 158
        if base < env.next_rob_entry:
            base += 160
        robs = tuple(RobPtr.encode(base + i // 2, former=not bool(i % 2)) for i in range(8))
        start = env.model.tail
        for i, flow in enumerate((16, 16, 16, 16, 16, 16, 16, 8)):
            await env.cycle(dispatch=env.build_dispatch((flow,), lanes=(lane,), robs=(robs[i],)))
        env.next_rob_entry = base + 4
        await env.cycle(redirect=Redirect(True, RobPtr.encode(base + 1), False))
        await env.settle_recovery()
        assert env.model.tail == start + 48
        assert await env.complete_and_drain() == tuple(range(start, start + 48))
        assert await fill_on_one_lane(env, 72, lane) == tuple(range(start + 48, start + 120))
        await env.idle(4)
        assert await env.complete_and_drain(newest_first=True) == tuple(range(start + 48, start + 120))


async def test_capacity_boundaries_eight_lanes_and_zero_flow(vlq):
    env = vlq
    await env.cycle(dispatch=env.build_dispatch((16, 16, 16, 16, 16, 16, 16, 6)))
    await env.idle(2)
    assert env.model.capacity == 2
    await env.cycle(dispatch=env.build_dispatch((1,), lanes=(7,)))
    await env.idle(2)
    assert env.model.capacity == 1
    await env.cycle(dispatch=env.build_dispatch((1,), lanes=(4,)))
    await env.idle(2)
    assert env.model.capacity == 0
    assert await env.complete_and_drain(newest_first=True) == tuple(range(120))
    old = env.model.head
    await env.cycle(dispatch=env.build_dispatch((0, 0), lanes=(0, 7)))
    await env.idle(4)
    assert env.observed.empty and env.observed.head == QueuePtr.encode(old)


@pytest.mark.parametrize("replay,update", ((True, True), (False, False), (True, False)))
async def test_replay_and_address_flags_hold_head_until_real_completion(vlq, replay, update):
    env = vlq
    await env.cycle(dispatch=env.build_dispatch((1,)))
    await env.cycle(writebacks={2: env.wb(0, replay=replay, update=update)})
    await env.idle(4)
    assert env.observed.head == QueuePtr() and not env.observed.empty and not env.observed.dequeue_valid
    await env.cycle(writebacks={1: env.wb(0)})
    assert await env.complete_and_drain() == (0,)


async def test_each_contiguous_prefix_length_and_nonrepeating_release(vlq):
    env = vlq
    for length in range(1, 9):
        start = env.model.tail
        await env.cycle(dispatch=env.build_dispatch((length + 1,), lanes=(length % 8,)))
        younger = list(range(start + 1, start + length))
        for i in range(0, len(younger), 3):
            await env.cycle(writebacks={lane: env.wb(pos) for lane, pos in enumerate(younger[i:i+3])})
        await env.idle(4)
        assert env.observed.head == QueuePtr.encode(start)
        await env.cycle(writebacks={0: env.wb(start)})
        history = await env.idle(3)
        assert tuple(len(change.reported) for change in history if change.reported) == (length,)
        assert env.observed.head == QueuePtr.encode(start + length)
        assert not env.observed.empty  # the deliberately uncompleted last slot
        assert await env.complete_and_drain() == (start + length,)


@pytest.mark.parametrize("flush_self", (False, True))
async def test_redirect_distinguishes_rob_slots_and_wrap_flags(vlq, flush_self):
    env = vlq
    robs = (RobPtr.encode(158), RobPtr.encode(159), RobPtr.encode(159, former=False), RobPtr.encode(160))
    await env.cycle(dispatch=env.build_dispatch((2, 3, 2, 1), robs=robs))
    env.next_rob_entry = 161
    retained = 2 if flush_self else 5
    await env.cycle(redirect=Redirect(True, RobPtr.encode(159), flush_self))
    assert env.observed.recovery_stall and not env.observed.recovery_valid
    await env.cycle()
    assert env.observed.recovery_stall and not env.observed.recovery_valid
    await env.cycle()
    assert env.observed.recovery_valid and env.observed.recovery_ptr == QueuePtr.encode(retained)
    assert env.observed.recovery_stall
    await env.cycle()
    assert not env.observed.recovery_valid and not env.observed.recovery_stall
    assert await env.complete_and_drain() == tuple(range(retained))
    await env.cycle(dispatch=env.build_dispatch((12,)))
    await env.idle(4)
    assert env.observed.head == QueuePtr.encode(retained)
    assert await env.complete_and_drain() == tuple(range(retained, retained + 12))


@pytest.mark.parametrize("mode", ("none", "all", "adjacent"))
async def test_redirect_none_all_and_adjacent_transactions(vlq, mode):
    env = vlq
    env.next_rob_entry = 10
    await env.cycle(dispatch=env.build_dispatch((2, 3, 4, 1)))
    if mode == "adjacent":
        await env.cycle(redirect=Redirect(True, RobPtr.encode(12), False))
        await env.cycle(redirect=Redirect(True, RobPtr.encode(10), True))
        responses = []
        for _ in range(3):
            await env.cycle()
            if env.observed.recovery_valid:
                responses.append(env.observed.recovery_ptr)
        assert responses == [QueuePtr.encode(9), QueuePtr.encode(0)]
        assert not env.observed.recovery_stall and env.observed.empty
    else:
        cutoff = 20 if mode == "none" else 9
        await env.cycle(redirect=Redirect(True, RobPtr.encode(cutoff), False))
        await env.settle_recovery()
        if mode == "none":
            assert await env.complete_and_drain() == tuple(range(10))
        else:
            assert not env.model.entries and env.observed.empty
    start = env.model.tail
    await env.cycle(dispatch=env.build_dispatch((8,)))
    await env.idle(3)
    assert await env.complete_and_drain() == tuple(range(start, start + 8))


async def test_dispatch_and_writeback_race_with_redirect(vlq):
    env = vlq
    env.next_rob_entry = 10
    await env.cycle(dispatch=env.build_dispatch((2, 2, 2)))
    # WB slot2 survives; WB slot4 is canceled. Incoming lanes0/7 are both
    # younger and reserved four slots, which must also be rolled back.
    await env.cycle(dispatch=env.build_dispatch((3, 1), lanes=(0, 7)),
                    writebacks={0: env.wb(2), 2: env.wb(4)},
                    redirect=Redirect(True, RobPtr.encode(11), False))
    await env.settle_recovery()
    assert env.model.tail == 4
    assert await env.complete_and_drain() == (0, 1, 2, 3)
    await env.cycle(dispatch=env.build_dispatch((8,)))
    await env.idle(4)
    assert env.observed.head == QueuePtr.encode(4)
    assert await env.complete_and_drain() == tuple(range(4, 12))


async def test_release_report_and_recovery_response_can_coincide(vlq):
    env = vlq
    env.next_rob_entry = 10
    await env.cycle(dispatch=env.build_dispatch((4, 4)))
    await env.cycle(writebacks={i: env.wb(i) for i in range(3)})
    await env.cycle(writebacks={0: env.wb(3)})
    await env.cycle(redirect=Redirect(True, RobPtr.encode(10), False))
    assert env.observed.dequeue_valid and env.observed.dequeue_count == 3
    assert env.observed.head == QueuePtr.encode(3)
    await env.cycle()
    await env.cycle()
    assert env.observed.dequeue_valid and env.observed.dequeue_count == 1
    assert env.observed.recovery_valid and env.observed.recovery_ptr == QueuePtr.encode(4)
    assert env.observed.head == QueuePtr.encode(4)
    await env.cycle()
    assert env.observed.empty and not env.observed.recovery_stall


@pytest.mark.parametrize("mode", ("active", "recovering"))
async def test_reset_cancels_owned_completed_and_recovery_state(vlq, mode):
    env = vlq
    await env.cycle(dispatch=env.build_dispatch((4, 4)))
    await env.cycle(writebacks={0: env.wb(0), 1: env.wb(1)})
    if mode == "recovering":
        await env.cycle(redirect=Redirect(True, RobPtr.encode(0), False))
        assert env.observed.recovery_stall
    await env.reset()
    assert env.observed.head == QueuePtr() and env.observed.empty and not env.observed.recovery_valid
    await env.cycle(dispatch=env.build_dispatch((3,), lanes=(7,)))
    await env.idle(4)
    assert env.observed.head == QueuePtr()
    assert await env.complete_and_drain() == (0, 1, 2)


async def test_disabled_payloads_do_not_complete_allocate_or_redirect(vlq):
    env = vlq
    await env.cycle(dispatch=env.build_dispatch((3,)))
    for phase in range(6):
        dispatch = {lane: Dispatch(False, RobPtr(bool(lane % 2), 150 + lane, bool(phase % 2)),
                                   QueuePtr(bool(phase % 2), 119 - lane), 16) for lane in range(8)}
        wbs = {lane: Writeback(False, (phase + lane) % 3, True, False) for lane in range(3)}
        await env.cycle(dispatch, wbs, redirect=Redirect(False, RobPtr.encode(159), True))
        assert env.observed.head == QueuePtr() and not env.observed.recovery_stall
    assert await env.complete_and_drain() == (0, 1, 2)


async def test_multiflow_interval_crosses_non_power_of_two_boundary(vlq):
    env = vlq
    await env.cycle(dispatch=env.build_dispatch((16, 16, 16, 16, 16, 16, 16, 5)))
    assert await env.complete_and_drain(newest_first=True) == tuple(range(117))
    change = await env.cycle(dispatch=env.build_dispatch((16,), lanes=(6,)))
    assert tuple(item.position for item in change.allocated) == tuple(range(117, 133))
    await env.idle(4)
    assert await env.complete_and_drain() == tuple(range(117, 133))
    assert env.observed.head == QueuePtr(True, 13)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_dispatch_completion_and_redirect(vlq, seed):
    env = vlq
    rng = random.Random(seed)
    for cycle in range(1400):
        if cycle == 700:
            await env.reset()
        live = list(env.model.entries.values())
        incomplete = [item for item in live if not item.completed]
        wbs = {}
        wb_count = min(len(incomplete), rng.randrange(4))
        for lane, item in zip(rng.sample(range(3), wb_count), rng.sample(incomplete, wb_count), strict=True):
            wbs[lane] = env.wb(item.position, replay=rng.random() < 0.15, update=rng.random() > 0.15)
        cutoff = rng.choice(live) if live and rng.random() < 0.08 else None
        redir = Redirect(True, cutoff.rob, rng.random() < 0.5) if cutoff else Redirect()
        dispatch = {}
        if not env.model.outputs.recovery_stall and env.model.capacity and rng.random() < 0.7:
            count = rng.randint(1, min(8, env.model.capacity))
            earliest = min((item.rob_order for item in live), default=None)
            # Keep the global ROB window legal independently of LQ capacity.
            if earliest is None or 2 * (env.next_rob_entry + count - 1) - earliest < 2 * env.spec["rob_entries"]:
                remaining = env.model.capacity
                flows = []
                for _ in range(count):
                    flow = rng.randint(0, min(16, remaining))
                    flows.append(flow)
                    remaining -= flow
                dispatch = env.build_dispatch(flows, lanes=sorted(rng.sample(range(8), count)))
        await env.cycle(dispatch, wbs, redirect=redir)
        if cutoff:
            env.next_rob_entry = cutoff.rob_order // 2 + 1
    await env.settle_recovery()
    await env.complete_and_drain(newest_first=True)
    assert env.observed.empty and env.model.head == env.model.tail
