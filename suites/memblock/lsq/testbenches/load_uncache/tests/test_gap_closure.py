"""Second gap analysis: real-child cancellation and FIFO return alignment."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.uncache_entry.transactions import RobPtr
from suites.memblock.lsq.testbenches.load_uncache.env.sequences import allocate_batch
from suites.memblock.lsq.testbenches.load_uncache.env.sequences import fill
from suites.memblock.lsq.testbenches.load_uncache.env.sequences import red


@pytest.mark.parametrize("phase", ("holding", "request", "wakeup"))
async def test_each_real_entry_cancellation_path_then_complete_new_generation(load_uncache, phase):
    env = load_uncache
    canceled_uids = []
    if phase in ("holding", "request"):
        seen = set()
        for rank in range(16):
            req = env.request(nc=False, rob=20, lq=20 + rank, tag=rank + 1)
            await env.enqueue({rank % 3: req}, pending=RobPtr.encode(19) if phase == "holding" else req.entry.rob)
            await env.cycle()
            slot, uid = env.slot(req), env.uid(req)
            seen.add(slot)
            canceled_uids.append(uid)
            if phase == "request":
                await env.cycle()
            assert env.owners[slot].phase == phase
            change = await env.redirect(RobPtr.encode(19))
            assert change["free"] == [slot]
            await env.idle(5)
        assert seen == set(range(16))
    else:
        # Real legal merge: identical address, attributes and byte masks.
        for offset in range(0, 16, 3):
            loads = {i: replace(env.request(nc=True, rob=10 + rank, lq=50 + rank, tag=1),
                                entry=replace(env.request(nc=True, rob=10 + rank, lq=50 + rank, tag=1).entry, mask=0x00FF))
                     for i, rank in enumerate(range(offset, min(offset + 3, 16)))}
            canceled_uids.extend(await allocate_batch(env, loads))
        await env.accept_all()
        for slot in range(16):
            await env.bind(slot, 3)
        await env.respond(3, 0x123456789ABCDEF0)
        assert all(owner.phase == "wakeup" for owner in env.owners.values())
        change = await env.redirect(RobPtr.encode(0))
        assert set(change["free"]) == set(range(16))
        await env.idle(7)
    env.arm("LQU-FLUSH.before_bus", canceled_uids, reuse=True)
    loads, completed = await fill(env)
    env.arm("LQU-REUSE.pool", completed)
    await env.drain()
    assert set(canceled_uids) <= env.canceled


async def test_return_bank_zero_when_pool_fifo_tail_is_fifteen(load_uncache):
    env = load_uncache
    loads, uids = await fill(env)
    await env.accept_all()
    for slot in range(16):
        await env.bind(slot, slot)
        await env.respond(slot, 0x100 + slot)
    await env.idle(20)
    for slot in range(1, 16):
        await env.bypass({slot % 3: loads[slot]})
        await env.idle(4)
    # Fifteen actual returns precede bank0's return, not just fifteen stimuli.
    assert env.pool_available == 15
    await env.bypass({2: loads[0]})
    await env.idle(6)
    new, reused = await fill(env)
    env.arm("LQU-CAPACITY.return", reused)
    env.arm("LQU-REUSE.pool", reused)
    await env.drain()


async def test_withdrawn_high_group_waiter_falls_back_to_current_candidates(load_uncache):
    env = load_uncache
    for slot in range(16):
        rob = 100 if slot == 9 else slot + 10
        req = env.request(nc=True, rob=rob, lq=slot + 60, paddr=0x345600000000 + slot * 0x1000, tag=slot + 1)
        await allocate_batch(env, {slot % 3: req})
    assert env.pipe_slot == 0
    change = await env.bus_ready()
    # Entry0 originally won while only the low group was present. That
    # acceptance leaves one further low-group preference before alternating.
    assert change["internal_slot"] == 1
    change = await env.bus_ready()
    # Slot 9 is still a live public owner when slot 8 is accepted, so the
    # withdrawn high-group waiter must fall back to the current candidate.
    assert change["internal_slot"] == 8 and 9 in env.owners
    uid = env.owners[9].uid
    await env.redirect(RobPtr.encode(50))
    assert 9 not in env.owners
    survivors = [owner.uid for owner in env.owners.values()]
    env.arm("LQU-ARB.withdrawn", survivors)
    env.arm("LQU-FLUSH.before_bus", [uid], reuse=True)
    await env.accept_all()
    await env.drain()


async def test_full_mid_width_unmatched_sid_and_out_of_order_responses(load_uncache):
    env = load_uncache
    loads, uids = await fill(env)
    await env.accept_all()
    for mid in range(16, 128):
        await env.id_only(mid, mid % 16)
    # No valid SID yet: arbitrary external responses must not produce wakeups.
    for sid in range(16):
        await env.respond(sid, 0xDEADBEEF)
        assert env.response.nc_wakeup is None
    for slot in range(16):
        await env.bind(slot, 15 - slot)
    for slot in reversed(range(16)):
        await env.respond(15 - slot, 1 << (slot * 4), error=bool(slot & 1), nderr=bool(slot & 2))
    await env.idle(20)
    env.arm("LQU-ID.bind", uids)
    env.arm("LQU-ID.route", uids)
    env.arm("LQU-WAKE.priority", uids)
    for slot in range(16):
        await env.consume(loads[slot], 1 << (slot * 4), lane=slot % 3, error=bool(slot & 1), nderr=bool(slot & 2))
