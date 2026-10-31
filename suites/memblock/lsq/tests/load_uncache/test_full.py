"""Coverage-gap expansion: actual 22-file parent with continuous checking."""

from dataclasses import asdict, replace
from itertools import permutations
import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.uncache_entry.types import QueuePtr, RobPtr, SOURCE_EXCEPTION_BITS
from suites.memblock.lsq.load_uncache.sequences import allocate_batch, fill, red


@pytest.mark.parametrize("nc", (False, True))
@pytest.mark.parametrize("lane", (0, 1, 2))
async def test_each_real_id_each_bypass_lane_and_type(load_uncache, nc, lane):
    env = load_uncache
    all_uids = []
    for slot in range(16):
        req = env.request(nc=nc, rob=20 + slot, lq=120 + slot, paddr=0x123456780000 + slot * 8, tag=slot + 1)
        await env.enqueue({slot % 3: req})
        await env.take_bus(req, slot)
        uid = env.uid(req)
        all_uids.append(uid)
        env.arm("LQU-EXCEPTION.truncation", [uid])
        await env.bind(slot, (slot + 1) % 16)
        data = (1 << (slot * 4)) | (1 << (slot * 4 + 3))
        await env.respond((slot + 1) % 16, data, error=bool(slot & 1), nderr=bool(slot & 2))
        await env.wait_wakeup(req)
        await env.consume(req, data, lane=lane, error=bool(slot & 1), nderr=bool(slot & 2))
    env.arm("LQU-ALLOC.all_ids", all_uids)
    assert len(env.completed) == 16


async def test_three_lane_six_permutations_sparse_and_rob_boundaries(load_uncache):
    env = load_uncache
    for rank, perm in enumerate(permutations(range(3))):
        loads = [env.request(rob=10 + i, lq=30 + i, tag=rank * 4 + i) for i in range(3)]
        uids = await allocate_batch(env, {lane: loads[index] for lane, index in enumerate(perm)})
        # Allocation order follows the reclaimed FIFO, not numeric slot order
        # after the pool wraps. The cycle checker checks the actual bus IDs.
        assert [tx["load"] for tx in env.last_change["allocated"]] == [asdict(load) for load in loads]
        env.arm("LQU-SORT.lanes", uids)
        await env.drain()
    for cases in ((RobPtr.encode(159), RobPtr.encode(160), RobPtr.encode(161)),
                  (RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), RobPtr.encode(11)),
                  (RobPtr.encode(10), RobPtr.encode(10), RobPtr.encode(10))):
        await env.reset()
        loads = [replace(env.request(rob=10, lq=40 + i, tag=i + 1), entry=replace(env.request().entry, rob=ptr, lq=QueuePtr.encode(40 + i), paddr=0x234500000000 + i * 0x1000)) for i, ptr in enumerate(cases)]
        uids = await allocate_batch(env, {2: loads[2], 0: loads[0], 1: loads[1]}, pending=cases[-1])
        env.arm("LQU-SORT.equal" if cases[0] == cases[-1] else "LQU-SORT.wrap", uids)
        await env.drain()
    for lane in range(3):
        uids = await allocate_batch(env, {lane: env.request(rob=80 + lane, lq=80 + lane)})
        env.arm("LQU-SORT.lanes", uids)
        await env.drain()


async def test_filter_each_exception_replay_and_type_then_prove_full_capacity(load_uncache):
    env = load_uncache
    for rank, bit in enumerate((*SOURCE_EXCEPTION_BITS, 19, 5)):
        req = env.request(rob=rank + 1, lq=rank + 1)
        await allocate_batch(env, {rank % 3: replace(req, entry=replace(req.entry, exceptions=1 << bit))})
        assert env.last_change["filtered"][0]["reason"] == "exception"
    req = env.request(rob=20, lq=20)
    await allocate_batch(env, {0: replace(req, need_replay=True, uncache_cause=False)})
    assert not env.model.owners
    await allocate_batch(env, {2: replace(req, entry=replace(req.entry, nc=False, mmio=False))})
    assert not env.model.owners
    await env.idle(5)
    assert env.model.pipe is None and not env.observed[P.p_uncache_req_valid]
    loads, uids = await fill(env)
    assert len(uids) == 16 and len(env.model.owners) == 16
    # Capacity proof for every rejected-by-filter input: all 16 owners still fit.
    for scene in ("LQU-FILTER.exception", "LQU-FILTER.replay", "LQU-FILTER.type"):
        env.arm(scene, uids)
    await env.drain()
    special = replace(env.request(lq=90), need_replay=True, uncache_cause=True)
    await allocate_batch(env, {1: special})
    await env.drain()


@pytest.mark.parametrize("remaining", (0, 1, 2))
async def test_partial_capacity_oldest_nack_and_recovery(load_uncache, remaining):
    env = load_uncache
    loads, uids = await fill(env, 16 - remaining)
    extra = [env.request(rob=80 + i, lq=80 + i, tag=65 + i) for i in range(3)]
    await allocate_batch(env, {0: extra[2], 1: extra[0], 2: extra[1]})
    assert len(env.last_change["allocated"]) == remaining
    assert len(env.last_change["rejected"]) == 3 - remaining
    assert env.observed[P.p_rollback_valid]
    assert env.observed[P.p_rollback_bits_robIdx_value] == extra[remaining].entry.rob.value
    before = set(env.model.owners)
    env.reach("LQU-CAPACITY.reject")
    env.reach("LQU-ROLLBACK.oldest")
    await env.drain(error=True, nderr=True)
    assert len(before) == 16
    # No hidden owners from the rejected requests; fresh full pool can complete.
    loads, recovered = await fill(env)
    env.arm("LQU-CAPACITY.reject", recovered)
    env.arm("LQU-ROLLBACK.oldest", recovered)
    env.arm("LQU-CAPACITY.return", recovered)
    env.arm("LQU-REUSE.pool", recovered)
    await env.drain()


async def test_three_bypass_lanes_same_owner_and_three_distinct_consumers(load_uncache):
    env = load_uncache
    loads, uids = await fill(env, 3)
    await env.accept_all()
    for slot in range(3):
        await env.bind(slot, slot)
        await env.respond(slot, 0xA0 + slot, error=bool(slot & 1), nderr=bool(slot & 2))
    await env.idle(5)
    change = await env.bypass({0: loads[0], 1: loads[0], 2: loads[0]})
    assert change["free"] == [0] and sum(item["consumed"] for item in change["entry_changes"]) == 1
    env.arm("LQU-BYPASS.lanes", [uids[0]])
    await env.idle(3)
    await env.bypass({0: loads[1], 2: loads[2]})
    env.arm("LQU-EXCEPTION.priority", uids[1:])
    assert env.observed[P.p_exceptionInfo_bits_robIdx_value] == loads[1].entry.rob.value
    await env.idle(5)
    # All three have real data in the following batch.
    uids = await allocate_batch(env, {i: env.request(rob=40 + i, lq=40 + i) for i in range(3)})
    await env.accept_all()
    for slot, tx in list(env.model.owners.items()):
        await env.bind(slot, slot)
        await env.respond(slot, 1 << slot)
    await env.idle(4)
    txs = list(env.model.owners.values())
    await env.bypass({i: tx.load for i, tx in enumerate(txs)})
    env.arm("LQU-BYPASS.lanes", uids)
    env.arm("LQU-EXCEPTION.priority", uids)
    await env.idle(5)


async def test_nonmatching_bypass_at_empty_response_and_wrong_identity(load_uncache):
    env = load_uncache
    req = env.request(lq=125)
    await env.bypass({0: req})
    assert not env.observed[P.p_bypass_0_s1Resp_valid]
    await allocate_batch(env, {2: req})
    await env.accept_all()
    uid = env.uid(req)
    await env.bind(0, 5)
    await env.bypass({0: req})  # not returned yet
    assert not env.observed[P.p_bypass_0_s1Resp_valid]
    await env.respond(5, 0x123)
    await env.wait_wakeup(req)
    for wrong in (replace(req, entry=replace(req.entry, nc=False, mmio=True)),
                  replace(req, entry=replace(req.entry, lq=QueuePtr(not req.entry.lq.flag, req.entry.lq.value))),
                  replace(req, entry=replace(req.entry, lq=QueuePtr(req.entry.lq.flag, req.entry.lq.value + 1)))):
        await env.bypass({1: wrong})
        assert not env.observed[P.p_bypass_1_s1Resp_valid]
    env.arm("LQU-BYPASS.miss", [uid])
    await env.consume(req, 0x123)
    await env.bypass({2: req})  # already consumed cannot be hit again
    assert not env.observed[P.p_bypass_2_s1Resp_valid]
    await env.idle(3)


async def test_nc_groups_elastic_hold_replace_and_fair_progress(load_uncache):
    env = load_uncache
    loads, uids = await fill(env)
    env.arm("LQU-PIPE.hold", uids)
    env.arm("LQU-PIPE.replace", uids)
    env.arm("LQU-ARB.nc_groups", uids)
    assert env.observed[P.p_uncache_req_valid]
    held = {key: value for key, value in env.observed.items() if key.startswith(P.p_uncache_req_)}
    for _ in range(8):
        await env.cycle()
        assert {key: value for key, value in env.observed.items() if key in held} == held
    accepted = await env.accept_all()
    assert len(accepted) == 16 and {slot for slot, uid in accepted} == set(range(16))
    # Both groups progress in this one real queue; exact sequence checked each edge.
    assert any(slot >= 8 for slot, _ in accepted[:5]) and any(slot < 8 for slot, _ in accepted[:5])
    await env.drain()
    env.arm("LQU-WAKE.priority", uids)


async def test_mmio_pending_and_priority_does_not_rewrite_buffered_nc(load_uncache):
    env = load_uncache
    nc = env.request(nc=True, lq=30, rob=10)
    mmio = env.request(nc=False, lq=31, rob=11)
    await allocate_batch(env, {0: nc}, pending=nc.entry.rob)
    await env.idle(3)
    assert env.observed[P.p_uncache_req_valid] and env.observed[P.p_uncache_req_bits_nc]
    await allocate_batch(env, {2: mmio}, pending=nc.entry.rob)
    await env.idle(4)
    assert not env.observed[P.p_rob_mmioBusy]
    await env.cycle(pending=mmio.entry.rob)
    await env.idle(2)
    assert env.observed[P.p_rob_mmioBusy]
    await env.take_bus(nc, 0)
    await env.take_bus(mmio, 1)
    uids = [env.uid(nc), env.uid(mmio)]
    env.arm("LQU-ARB.mmio_priority", uids)
    await env.bind(0, 2)
    await env.bind(1, 3)
    later_nc = env.request(nc=True, rob=12, lq=32)
    await allocate_batch(env, {0: later_nc}, pending=mmio.entry.rob)
    for _ in range(5):
        await env.cycle({P.p_uncache_req_ready: 1})
        assert not env.observed[P.p_uncache_req_valid]
    await env.respond(3, 0x76543210)
    await env.wait_wakeup(mmio)
    await env.consume(mmio, 0x76543210)
    await env.accept_all()
    await env.drain()


@pytest.mark.parametrize("distance", (0, 1, 2))
async def test_redirect_filter_windows_do_not_allocate_hidden_entries(load_uncache, distance):
    env = load_uncache
    q = env.request(nc=True, rob=20, lq=40)
    if distance == 0:
        # Current redirect at save edge also becomes the prior redirect at allocate.
        await env.enqueue({2: q}, controls=red(RobPtr.encode(19)))
    else:
        await env.enqueue({2: q})
        if distance == 1:
            await env.cycle(red(RobPtr.encode(19)))
        else:
            await env.cycle()
            await env.cycle(red(RobPtr.encode(19)))
    await env.idle(5)
    assert not env.model.owners
    loads, uids = await fill(env)
    env.arm("LQU-FILTER.redirect", uids)
    await env.drain()


@pytest.mark.parametrize("phase", ("saved", "holding", "request", "buffered", "response", "wakeup", "output"))
async def test_redirect_phase_and_reset_reuse(load_uncache, phase):
    env = load_uncache
    nc = phase not in ("holding", "request")
    req = env.request(nc=nc, rob=20, lq=20)
    await env.enqueue({0: req}, pending=RobPtr.encode(19) if phase == "holding" else req.entry.rob)
    if phase != "saved":
        await env.cycle()
    if phase in ("request", "buffered", "response", "wakeup", "output"):
        await env.cycle()  # become request, before internal capture
    if phase in ("buffered", "response", "wakeup", "output"):
        await env.cycle()  # captured in elastic buffer
    if phase in ("response", "wakeup", "output"):
        await env.take_bus(req, 0)
        await env.bind(0, 5)
    if phase in ("wakeup", "output"):
        await env.respond(5, 0x7777)
    if phase == "output":
        await env.wait_wakeup(req)
    uids = [tx.uid for tx in env.model.owners.values()]
    env.arm("LQU-FLUSH.inflight" if phase in ("buffered", "response") else "LQU-FLUSH.before_bus", uids, reuse=True)
    await env.cycle(red(RobPtr.encode(19)))
    if phase == "buffered":
        # The captured request is NOT killed by redirect. It must still issue.
        await env.take_bus(req, 0)
        await env.bind(0, 5)
        await env.respond(5, 0x7777)
    elif phase == "response":
        await env.idle(4)
        assert env.model.owners
        await env.respond(5, 0x7777)
    await env.idle(5)
    assert not env.model.owners and not env.model.external
    new = env.request(nc=not nc, rob=21, lq=21)
    await allocate_batch(env, {1: new}, pending=new.entry.rob)
    await env.drain()
    # A separate active reset at each corresponding stage is still required.
    await env.enqueue({2: req}, pending=req.entry.rob)
    await env.idle(4)
    await env.reset()
    await allocate_batch(env, {0: env.request(rob=30, lq=30)})
    await env.drain()


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_concurrent_batches_backpressure_and_reuse(load_uncache, seed):
    env = load_uncache
    rng = random.Random(seed)
    for round_id in range(10):
        requests = []
        for i in range(16):
            req = env.request(nc=True, rob=140 + i, lq=(round_id * 16 + i) % 240, paddr=rng.randrange(1 << 48), tag=i + round_id * 16)
            req = replace(req, entry=replace(req.entry, mask=rng.randrange(1 << 16), rob=RobPtr.encode(140 + i, former=bool(rng.randrange(2)))))
            requests.append(req)
        for start in range(0, 16, 3):
            batch = requests[start:start + 3]
            lanes = rng.sample(range(3), len(batch))
            await env.enqueue(dict(zip(lanes, batch, strict=True)), pending=RobPtr.encode(159))
            await env.idle(rng.randrange(1, 4))
        await env.accept_all(stall=rng.randrange(8))
        uids = [tx.uid for tx in env.model.owners.values()]
        env.arm("LQU-REUSE.pool", uids)
        slots = list(env.model.owners)
        rng.shuffle(slots)
        for slot in slots:
            await env.bind(slot, (slot + round_id) % 16)
        for slot in slots:
            await env.respond((slot + round_id) % 16, rng.randrange(1 << 64), error=bool(rng.randrange(2)), nderr=bool(rng.randrange(2)))
            await env.idle(rng.randrange(3))
        await env.idle(18)
        rng.shuffle(slots)
        for offset in range(0, 16, 3):
            loads = [env.model.owners[slot].load for slot in slots[offset:offset + 3]]
            await env.bypass(dict(enumerate(loads)))
        await env.idle(5)
        assert not env.model.owners and not env.model.external
