"""Reset phases, historical recovery, slot age and same-edge consumption."""

import pytest

from dataclasses import replace
from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.uncache_entry.types import RobPtr
from suites.memblock.lsq.load_uncache.sequences import allocate_batch, fill, red


async def phase_setup(env, phase):
    req = env.request(nc=phase not in ("holding", "request"), rob=20, lq=20)
    await env.enqueue({0: req}, pending=RobPtr.encode(19) if phase == "holding" else req.entry.rob)
    if phase != "saved":
        await env.cycle()
    if phase in ("request", "buffered", "response", "wakeup", "output"):
        await env.cycle()
    if phase in ("buffered", "response", "wakeup", "output"):
        await env.cycle()
    if phase in ("response", "wakeup", "output"):
        await env.take_bus(req, 0)
        await env.bind(0, 7)
    if phase in ("wakeup", "output"):
        await env.respond(7, 0x0123456789ABCDEF, error=True, nderr=True)
    if phase == "output":
        await env.wait_wakeup(req)
    if phase in ("holding", "request", "response", "wakeup", "output"):
        assert env.model.entries[0].phase == phase
    if phase == "buffered":
        assert env.model.pipe is not None and not env.model.external
    return req


@pytest.mark.parametrize("phase", ("saved", "holding", "request", "buffered", "response", "wakeup", "output"))
async def test_active_reset_exact_phases_then_new_complete_owner(load_uncache, phase):
    env = load_uncache
    await phase_setup(env, phase)
    await env.reset()
    req = env.request(nc=True, rob=21, lq=21)
    await allocate_batch(env, {2: req}, pending=req.entry.rob)
    await env.drain()


@pytest.mark.parametrize("distance", (0, 1, 2, 3))
async def test_capacity_rollback_current_and_two_historical_redirects(load_uncache, distance):
    env = load_uncache
    loads, uids = await fill(env)
    requests = {i: env.request(rob=80 + i, lq=80 + i, tag=64 + i) for i in range(3)}
    if distance >= 2:
        await env.cycle(red(RobPtr.encode(50)))
        await env.idle(distance - 2)
    await env.enqueue(requests, pending=RobPtr.encode(140), controls=red(RobPtr.encode(50)) if distance == 1 else None)
    change = await env.cycle(red(RobPtr.encode(50)) if distance == 0 else None)
    assert env.observed[P.p_rollback_valid] == int(distance == 3)
    if distance >= 2:
        assert len(change["rejected"]) == 3
    env.arm("LQU-ROLLBACK.redirect_window", uids)
    await env.drain()


@pytest.mark.parametrize("nc", (False, True))
async def test_current_redirect_with_bypass_consumption_has_report(load_uncache, nc):
    env = load_uncache
    req = env.request(nc=nc, rob=20, lq=20)
    await allocate_batch(env, {0: req}, pending=req.entry.rob)
    await env.take_bus(req, 0)
    await env.bind(0, 3)
    await env.respond(3, 0x9876543210ABCDEF, error=True, nderr=True)
    await env.wait_wakeup(req)
    uid = env.uid(req)
    fields = red(req.entry.rob, True)
    fields.update(io_bypass_1_s0Req_valid=1, io_bypass_1_s0Req_bits_lqIdx_flag=req.entry.lq.flag,
                  io_bypass_1_s0Req_bits_lqIdx_value=req.entry.lq.value, io_bypass_1_s0Req_bits_isNCReplay=nc,
                  io_bypass_1_s0Req_bits_isMMIOReplay=not nc)
    change = await env.cycle(fields)
    assert change["free"] == [0] and change["entry_changes"][0]["consumed"]
    assert env.observed[P.p_bypass_1_s1Resp_valid] and env.observed[P.p_exceptionInfo_valid]
    await env.idle(3)
    env.arm("LQU-FLUSH.consume_concurrent", [uid])


@pytest.mark.parametrize("case", range(6))
async def test_redirect_same_entry_former_latter_and_wrap(load_uncache, case):
    env = load_uncache
    cases = ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), False, False),
             (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False, True),
             (RobPtr.encode(10), RobPtr.encode(10), False, False),
             (RobPtr.encode(10), RobPtr.encode(10), True, True),
             (RobPtr.encode(160), RobPtr.encode(159), False, True),
             (RobPtr.encode(159), RobPtr.encode(160), False, False))
    owner_rob, cutoff, self_flush, cancel = cases[case]
    base = env.request(rob=10, lq=10)
    req = replace(base, entry=replace(base.entry, rob=owner_rob))
    await allocate_batch(env, {2: req}, pending=owner_rob)
    await env.cycle()
    uid = env.uid(req)
    change = await env.cycle(red(cutoff, self_flush))
    assert (uid in env.canceled) == cancel
    if not cancel:
        await env.drain()
    else:
        env.arm("LQU-FLUSH.before_bus", [uid], reuse=True)
        await allocate_batch(env, {0: env.request(rob=20, lq=20)})
        await env.drain()


async def test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim(load_uncache):
    env = load_uncache
    # Explicit UNIT-INTERFACE boundary, not normal ROB commit traffic: pending
    # beyond both active MMIO loads. The ordinary priority test uses legal ROB.
    env.reach("LQU-ARB.mmio_selector_boundary")
    a, b = (env.request(nc=False, rob=10 + i, lq=20 + i, tag=i + 1) for i in range(2))
    await allocate_batch(env, {0: a, 1: b}, pending=RobPtr.encode(20))
    await env.take_bus(b, 1)  # later elaborated selector has priority
    await env.bind(1, 3)
    await env.respond(3, 0xBBBB)
    await env.wait_wakeup(b)
    uid_b, uid_a = env.uid(b), env.uid(a)
    await env.consume(b, 0xBBBB)
    await env.take_bus(a, 0)
    await env.bind(0, 4)
    await env.respond(4, 0xAAAA)
    await env.wait_wakeup(a)
    await env.consume(a, 0xAAAA)
    env.arm("LQU-ARB.mmio_selector_boundary", [uid_a, uid_b])
