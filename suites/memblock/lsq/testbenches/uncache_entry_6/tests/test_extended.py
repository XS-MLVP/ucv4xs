"""Protocol-semantic expansion for every real entry ID, never a substitute DUT."""
from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import IdResponse
from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import Redirect
from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import Request
from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import Response
from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import RobPtr
from suites.memblock.lsq.testbenches.uncache_entry_6.transactions import SOURCE_EXCEPTION_BITS


async def prepare_phase(env, request, phase, *, sid=5):
    pending = RobPtr.encode(int(request.rob.flag) * 160 + request.rob.value - 1) if phase == "holding" and not request.nc else request.rob
    await env.cycle(request, pending=pending)
    if phase == "holding":
        return
    await env.cycle()
    assert env.observed.bus.valid
    if phase == "request":
        return
    await env.issue()
    await env.cycle(id_response=IdResponse(True, env.spec["entry_id"], sid))
    if phase == "response":
        return
    await env.cycle(response=Response(True, 0xFEDCBA9876543210, True, True))
    if phase == "wakeup":
        return
    await env.cycle()
    assert env.observed.nc.valid if request.nc else env.observed.mmio.valid


async def reuse_and_complete(env, *, nc, tag=99):
    await env.idle(3)
    assert not any((env.observed.bus.valid, env.observed.mmio_wakeup.valid, env.observed.nc_wakeup.valid,
                    env.observed.mmio.valid, env.observed.nc.valid, env.observed.exception.valid, env.observed.slave_valid))
    req = env.request(nc=nc, tag=tag, lq=135)
    await env.cycle(req, pending=req.rob)
    assert not env.observed.slave_valid
    await env.complete(data=0x13579BDF2468ACE0, sid=12)


async def test_all_mid_values_all_sid_values_and_repeated_type_reuse(uncache_entry_6):
    await uncache_entry_6.cycle(id_response=IdResponse(True, uncache_entry_6.spec["entry_id"], 15))
    assert not uncache_entry_6.observed.slave_valid
    for sid in range(16):
        req = uncache_entry_6.request(nc=bool(sid % 2), rob=RobPtr.encode(20 + sid), lq=117 + sid,
                            paddr=0x123456780000 + sid * 8, tag=sid + 64, exceptions=1 << SOURCE_EXCEPTION_BITS[sid % 8])
        await uncache_entry_6.cycle(req, pending=req.rob)
        assert not uncache_entry_6.observed.slave_valid
        await uncache_entry_6.issue()
        if sid == 0:
            for mid in range(128):
                if mid != uncache_entry_6.spec["entry_id"]:
                    await uncache_entry_6.cycle(id_response=IdResponse(True, mid, (mid + 3) % 16))
                    assert not uncache_entry_6.observed.slave_valid
        await uncache_entry_6.complete(sid=sid, data=(0x0123456789ABCDEF ^ (sid << 56)), error=bool(sid & 2), nderr=bool(sid & 1))


async def test_mask_halves_single_bytes_and_all_64_data_bits(uncache_entry_6):
    for bit in range(16):
        high = bit >= 8
        mask = (1 << bit) | (0x5A if high else 0xA500)
        req = uncache_entry_6.request(nc=bool(bit % 2), paddr=0xABCDEF010000 + 8 * int(high), mask=mask, tag=bit + 16)
        await uncache_entry_6.cycle(req, pending=req.rob)
        await uncache_entry_6.complete(data=1 << ((bit * 5) % 64), sid=bit)
    for bit in range(64):
        req = uncache_entry_6.request(nc=bool(bit % 2), paddr=0xABCDEF010000 + 8 * (bit % 2), tag=bit + 128)
        await uncache_entry_6.cycle(req, pending=req.rob)
        await uncache_entry_6.complete(data=1 << bit, sid=bit % 16)


async def test_mmio_registered_pending_and_logical_rob_boundaries(uncache_entry_6):
    req = uncache_entry_6.request(nc=False, rob=RobPtr.encode(10))
    await uncache_entry_6.cycle(req, pending=RobPtr.encode(9))
    for _ in range(5):
        await uncache_entry_6.cycle()
        assert not uncache_entry_6.observed.bus.valid
    await uncache_entry_6.cycle(pending=req.rob)
    assert not uncache_entry_6.observed.bus.valid  # current pending is not yet permission
    await uncache_entry_6.cycle()
    assert uncache_entry_6.observed.bus.valid
    await uncache_entry_6.complete()
    for rob, pending, allowed in ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), True),
                                 (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False),
                                 (RobPtr.encode(160), RobPtr.encode(159), False),
                                 (RobPtr.encode(159), RobPtr.encode(160), True)):
        req = uncache_entry_6.request(nc=False, rob=rob, tag=33)
        await uncache_entry_6.cycle(req, pending=pending)
        await uncache_entry_6.cycle()
        assert uncache_entry_6.observed.bus.valid == allowed
        if not allowed:
            await uncache_entry_6.cycle(pending=rob)
            assert not uncache_entry_6.observed.bus.valid
            await uncache_entry_6.cycle()
            assert uncache_entry_6.observed.bus.valid
        await uncache_entry_6.complete()


@pytest.mark.parametrize("nc", (False, True))
async def test_bus_wakeup_and_consumer_backpressure_hold_payload(uncache_entry_6, nc):
    req = uncache_entry_6.request(nc=nc, lq=239, tag=7)
    await uncache_entry_6.cycle(req, pending=req.rob)
    await uncache_entry_6.cycle()
    assert uncache_entry_6.observed.bus.valid
    poison = replace(uncache_entry_6.request(nc=not nc, tag=31), valid=False)
    for _ in range(8):
        await uncache_entry_6.cycle(poison)
        assert uncache_entry_6.observed.bus.valid
    await uncache_entry_6.cycle(bus_ready=True, id_response=IdResponse(True, uncache_entry_6.spec["entry_id"], 14))
    assert uncache_entry_6.observed.slave_valid and uncache_entry_6.observed.slave_id == 14
    for _ in range(7):
        await uncache_entry_6.cycle()
        assert not any((uncache_entry_6.observed.mmio_wakeup.valid, uncache_entry_6.observed.nc_wakeup.valid, uncache_entry_6.observed.mmio.valid, uncache_entry_6.observed.nc.valid))
    await uncache_entry_6.cycle(response=Response(True, 0x8000000000000001, False, True))
    if uncache_entry_6.spec["wakeup_backpressure"]:
        for _ in range(6):
            await uncache_entry_6.cycle(mmio_wake_ready=nc, nc_wake_ready=not nc)
            assert uncache_entry_6.observed.nc_wakeup.valid if nc else uncache_entry_6.observed.mmio_wakeup.valid
            assert not uncache_entry_6.observed.mmio.valid and not uncache_entry_6.observed.nc.valid
    await uncache_entry_6.cycle()
    for _ in range(8):
        await uncache_entry_6.cycle(nc_ready=not nc, mmio_ready=nc)
        out = uncache_entry_6.observed.nc if nc else uncache_entry_6.observed.mmio
        assert out.valid and out.data == 0x8000000000000001 and out.nderr and not out.error
        assert uncache_entry_6.observed.slave_valid and uncache_entry_6.observed.slave_id == 14
    await uncache_entry_6.complete()


@pytest.mark.parametrize("phase", ("holding", "request", "response", "wakeup", "output"))
@pytest.mark.parametrize("nc", (False, True))
async def test_redirect_each_protocol_phase_then_safe_reuse(uncache_entry_6, phase, nc):
    req = uncache_entry_6.request(nc=nc, rob=RobPtr.encode(10), tag=17)
    await prepare_phase(uncache_entry_6, req, phase)
    redirect = Redirect(True, RobPtr.encode(9), False)
    change = await uncache_entry_6.cycle(redirect=redirect)
    if phase == "response":
        assert not change.retired and uncache_entry_6.model.owner is not None
        for _ in range(4):
            await uncache_entry_6.cycle()
            assert uncache_entry_6.model.owner is not None and not uncache_entry_6.observed.nc_wakeup.valid and not uncache_entry_6.observed.mmio_wakeup.valid
        change = await uncache_entry_6.cycle(response=Response(True, 0xDEADBEEF, True, False))
        assert change.retired and uncache_entry_6.model.owner is None
    else:
        assert change.retired and uncache_entry_6.model.owner is None
        if phase == "wakeup":
            assert change.woke  # current redirect is not a combinational wakeup valid gate
    await reuse_and_complete(uncache_entry_6, nc=not nc)
    if phase == "response":
        # Current redirect and response also cancel together without relying
        # on a previously latched cancellation pulse.
        await prepare_phase(uncache_entry_6, req, "response")
        change = await uncache_entry_6.cycle(redirect=redirect, response=Response(True, 0xAA55, False, True))
        assert change.retired
        await reuse_and_complete(uncache_entry_6, nc=not nc, tag=101)


@pytest.mark.parametrize("nc", (False, True))
async def test_current_redirect_and_data_consume_still_report(uncache_entry_6, nc):
    req = uncache_entry_6.request(nc=nc)
    await prepare_phase(uncache_entry_6, req, "output")
    change = await uncache_entry_6.cycle(redirect=Redirect(True, RobPtr.encode(9), False), nc_ready=nc, mmio_ready=not nc)
    assert change.retired and change.consumed and uncache_entry_6.observed.exception.valid
    assert uncache_entry_6.observed.exception.rob == req.rob
    await reuse_and_complete(uncache_entry_6, nc=not nc)


async def test_redirect_former_latter_same_slot_and_rob_wrap(uncache_entry_6):
    cases = ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), False, False),
             (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False, True),
             (RobPtr.encode(10, former=True), RobPtr.encode(10, former=True), False, False),
             (RobPtr.encode(10, former=True), RobPtr.encode(10, former=True), True, True),
             (RobPtr.encode(160), RobPtr.encode(159), False, True),
             (RobPtr.encode(159), RobPtr.encode(160), False, False))
    for rob, cutoff, flush_self, canceled in cases:
        req = uncache_entry_6.request(nc=True, rob=rob)
        await prepare_phase(uncache_entry_6, req, "request")
        change = await uncache_entry_6.cycle(redirect=Redirect(True, cutoff, flush_self))
        assert change.retired == canceled
        if canceled:
            await reuse_and_complete(uncache_entry_6, nc=False)
        else:
            assert uncache_entry_6.observed.bus.valid
            await uncache_entry_6.complete()


async def test_reset_at_all_transaction_phases_and_disabled_payloads(uncache_entry_6):
    for rank, phase in enumerate(("holding", "request", "response", "wakeup", "output")):
        req = uncache_entry_6.request(nc=bool(rank % 2), tag=rank + 1)
        await prepare_phase(uncache_entry_6, req, phase)
        await uncache_entry_6.reset()
        poison = replace(req, valid=False, exceptions=sum(1 << bit for bit in SOURCE_EXCEPTION_BITS))
        await uncache_entry_6.cycle(poison, id_response=IdResponse(False, 127, 15), response=Response(False, (1 << 64) - 1, True, True),
                          redirect=Redirect(False, RobPtr.encode(159), True))
        await reuse_and_complete(uncache_entry_6, nc=not req.nc, tag=rank + 80)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_protocol_lifecycles(uncache_entry_6, seed):
    rng = random.Random(seed + uncache_entry_6.spec["entry_id"] * 1009)
    for rank in range(80):
        nc = bool(rng.randrange(2))
        req = uncache_entry_6.request(nc=nc, rob=RobPtr.encode(rank + 150, former=bool(rank % 2)), lq=rng.randrange(240),
                            paddr=rng.randrange(1 << 48), mask=rng.randrange(1 << 16), tag=rank + 96,
                            exceptions=sum((rng.randrange(2) << bit) for bit in SOURCE_EXCEPTION_BITS))
        pending = RobPtr.encode(rank + 149) if not nc else req.rob
        await uncache_entry_6.cycle(req, pending=pending)
        if not nc:
            await uncache_entry_6.idle(rng.randrange(1, 6))
            await uncache_entry_6.cycle(pending=req.rob)
        while not uncache_entry_6.observed.bus.valid:
            await uncache_entry_6.cycle()
        await uncache_entry_6.idle(rng.randrange(6))
        if rng.random() < 0.15:
            await uncache_entry_6.cycle(redirect=Redirect(True, req.rob, True))
            await reuse_and_complete(uncache_entry_6, nc=not nc, tag=rank + 100)
            continue
        await uncache_entry_6.issue()
        await uncache_entry_6.cycle(id_response=IdResponse(True, uncache_entry_6.spec["entry_id"], rng.randrange(16)))
        await uncache_entry_6.idle(rng.randrange(7))
        cancel = rng.random() < 0.2
        if cancel:
            await uncache_entry_6.cycle(redirect=Redirect(True, req.rob, True))
            await uncache_entry_6.idle(rng.randrange(1, 5))
        await uncache_entry_6.cycle(response=Response(True, rng.randrange(1 << 64), bool(rng.randrange(2)), bool(rng.randrange(2))))
        if cancel:
            await reuse_and_complete(uncache_entry_6, nc=not nc, tag=rank + 200)
            continue
        if uncache_entry_6.spec["wakeup_backpressure"]:
            await uncache_entry_6.idle(rng.randrange(6), mmio_wake_ready=False, nc_wake_ready=False)
        await uncache_entry_6.cycle()
        await uncache_entry_6.idle(rng.randrange(6))
        await uncache_entry_6.complete()
    assert uncache_entry_6.model.owner is None
