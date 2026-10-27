"""Protocol-semantic expansion for every real entry ID, never a substitute DUT."""
from dataclasses import replace
import random

import pytest

from lsqverify.uncache_entry.types import IdResponse, Redirect, Request, Response, RobPtr, SOURCE_EXCEPTION_BITS


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


async def test_all_mid_values_all_sid_values_and_repeated_type_reuse(entry):
    await entry.cycle(id_response=IdResponse(True, entry.spec["entry_id"], 15))
    assert not entry.observed.slave_valid
    for sid in range(16):
        req = entry.request(nc=bool(sid % 2), rob=RobPtr.encode(20 + sid), lq=117 + sid,
                            paddr=0x123456780000 + sid * 8, tag=sid + 64, exceptions=1 << SOURCE_EXCEPTION_BITS[sid % 8])
        await entry.cycle(req, pending=req.rob)
        assert not entry.observed.slave_valid
        await entry.issue()
        if sid == 0:
            for mid in range(128):
                if mid != entry.spec["entry_id"]:
                    await entry.cycle(id_response=IdResponse(True, mid, (mid + 3) % 16))
                    assert not entry.observed.slave_valid
        await entry.complete(sid=sid, data=(0x0123456789ABCDEF ^ (sid << 56)), error=bool(sid & 2), nderr=bool(sid & 1))


async def test_mask_halves_single_bytes_and_all_64_data_bits(entry):
    for bit in range(16):
        high = bit >= 8
        mask = (1 << bit) | (0x5A if high else 0xA500)
        req = entry.request(nc=bool(bit % 2), paddr=0xABCDEF010000 + 8 * int(high), mask=mask, tag=bit + 16)
        await entry.cycle(req, pending=req.rob)
        await entry.complete(data=1 << ((bit * 5) % 64), sid=bit)
    for bit in range(64):
        req = entry.request(nc=bool(bit % 2), paddr=0xABCDEF010000 + 8 * (bit % 2), tag=bit + 128)
        await entry.cycle(req, pending=req.rob)
        await entry.complete(data=1 << bit, sid=bit % 16)


async def test_mmio_registered_pending_and_logical_rob_boundaries(entry):
    req = entry.request(nc=False, rob=RobPtr.encode(10))
    await entry.cycle(req, pending=RobPtr.encode(9))
    for _ in range(5):
        await entry.cycle()
        assert not entry.observed.bus.valid
    await entry.cycle(pending=req.rob)
    assert not entry.observed.bus.valid  # current pending is not yet permission
    await entry.cycle()
    assert entry.observed.bus.valid
    await entry.complete()
    for rob, pending, allowed in ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), True),
                                 (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False),
                                 (RobPtr.encode(160), RobPtr.encode(159), False),
                                 (RobPtr.encode(159), RobPtr.encode(160), True)):
        req = entry.request(nc=False, rob=rob, tag=33)
        await entry.cycle(req, pending=pending)
        await entry.cycle()
        assert entry.observed.bus.valid == allowed
        if not allowed:
            await entry.cycle(pending=rob)
            assert not entry.observed.bus.valid
            await entry.cycle()
            assert entry.observed.bus.valid
        await entry.complete()


@pytest.mark.parametrize("nc", (False, True))
async def test_bus_wakeup_and_consumer_backpressure_hold_payload(entry, nc):
    req = entry.request(nc=nc, lq=239, tag=7)
    await entry.cycle(req, pending=req.rob)
    await entry.cycle()
    assert entry.observed.bus.valid
    poison = replace(entry.request(nc=not nc, tag=31), valid=False)
    for _ in range(8):
        await entry.cycle(poison)
        assert entry.observed.bus.valid
    await entry.cycle(bus_ready=True, id_response=IdResponse(True, entry.spec["entry_id"], 14))
    assert entry.observed.slave_valid and entry.observed.slave_id == 14
    for _ in range(7):
        await entry.cycle()
        assert not any((entry.observed.mmio_wakeup.valid, entry.observed.nc_wakeup.valid, entry.observed.mmio.valid, entry.observed.nc.valid))
    await entry.cycle(response=Response(True, 0x8000000000000001, False, True))
    if entry.spec["wakeup_backpressure"]:
        for _ in range(6):
            await entry.cycle(mmio_wake_ready=nc, nc_wake_ready=not nc)
            assert entry.observed.nc_wakeup.valid if nc else entry.observed.mmio_wakeup.valid
            assert not entry.observed.mmio.valid and not entry.observed.nc.valid
    await entry.cycle()
    for _ in range(8):
        await entry.cycle(nc_ready=not nc, mmio_ready=nc)
        out = entry.observed.nc if nc else entry.observed.mmio
        assert out.valid and out.data == 0x8000000000000001 and out.nderr and not out.error
        assert entry.observed.slave_valid and entry.observed.slave_id == 14
    await entry.complete()


@pytest.mark.parametrize("phase", ("holding", "request", "response", "wakeup", "output"))
@pytest.mark.parametrize("nc", (False, True))
async def test_redirect_each_protocol_phase_then_safe_reuse(entry, phase, nc):
    req = entry.request(nc=nc, rob=RobPtr.encode(10), tag=17)
    await prepare_phase(entry, req, phase)
    redirect = Redirect(True, RobPtr.encode(9), False)
    change = await entry.cycle(redirect=redirect)
    if phase == "response":
        assert not change.retired and entry.model.owner is not None
        for _ in range(4):
            await entry.cycle()
            assert entry.model.owner is not None and not entry.observed.nc_wakeup.valid and not entry.observed.mmio_wakeup.valid
        change = await entry.cycle(response=Response(True, 0xDEADBEEF, True, False))
        assert change.retired and entry.model.owner is None
    else:
        assert change.retired and entry.model.owner is None
        if phase == "wakeup":
            assert change.woke  # current redirect is not a combinational wakeup valid gate
    await reuse_and_complete(entry, nc=not nc)
    if phase == "response":
        # Current redirect and response also cancel together without relying
        # on a previously latched cancellation pulse.
        await prepare_phase(entry, req, "response")
        change = await entry.cycle(redirect=redirect, response=Response(True, 0xAA55, False, True))
        assert change.retired
        await reuse_and_complete(entry, nc=not nc, tag=101)


@pytest.mark.parametrize("nc", (False, True))
async def test_current_redirect_and_data_consume_still_report(entry, nc):
    req = entry.request(nc=nc)
    await prepare_phase(entry, req, "output")
    change = await entry.cycle(redirect=Redirect(True, RobPtr.encode(9), False), nc_ready=nc, mmio_ready=not nc)
    assert change.retired and change.consumed and entry.observed.exception.valid
    assert entry.observed.exception.rob == req.rob
    await reuse_and_complete(entry, nc=not nc)


async def test_redirect_former_latter_same_slot_and_rob_wrap(entry):
    cases = ((RobPtr.encode(10, former=True), RobPtr.encode(10, former=False), False, False),
             (RobPtr.encode(10, former=False), RobPtr.encode(10, former=True), False, True),
             (RobPtr.encode(10, former=True), RobPtr.encode(10, former=True), False, False),
             (RobPtr.encode(10, former=True), RobPtr.encode(10, former=True), True, True),
             (RobPtr.encode(160), RobPtr.encode(159), False, True),
             (RobPtr.encode(159), RobPtr.encode(160), False, False))
    for rob, cutoff, flush_self, canceled in cases:
        req = entry.request(nc=True, rob=rob)
        await prepare_phase(entry, req, "request")
        change = await entry.cycle(redirect=Redirect(True, cutoff, flush_self))
        assert change.retired == canceled
        if canceled:
            await reuse_and_complete(entry, nc=False)
        else:
            assert entry.observed.bus.valid
            await entry.complete()


async def test_reset_at_all_transaction_phases_and_disabled_payloads(entry):
    for rank, phase in enumerate(("holding", "request", "response", "wakeup", "output")):
        req = entry.request(nc=bool(rank % 2), tag=rank + 1)
        await prepare_phase(entry, req, phase)
        await entry.reset()
        poison = replace(req, valid=False, exceptions=sum(1 << bit for bit in SOURCE_EXCEPTION_BITS))
        await entry.cycle(poison, id_response=IdResponse(False, 127, 15), response=Response(False, (1 << 64) - 1, True, True),
                          redirect=Redirect(False, RobPtr.encode(159), True))
        await reuse_and_complete(entry, nc=not req.nc, tag=rank + 80)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_protocol_lifecycles(entry, seed):
    rng = random.Random(seed + entry.spec["entry_id"] * 1009)
    for rank in range(80):
        nc = bool(rng.randrange(2))
        req = entry.request(nc=nc, rob=RobPtr.encode(rank + 150, former=bool(rank % 2)), lq=rng.randrange(240),
                            paddr=rng.randrange(1 << 48), mask=rng.randrange(1 << 16), tag=rank + 96,
                            exceptions=sum((rng.randrange(2) << bit) for bit in SOURCE_EXCEPTION_BITS))
        pending = RobPtr.encode(rank + 149) if not nc else req.rob
        await entry.cycle(req, pending=pending)
        if not nc:
            await entry.idle(rng.randrange(1, 6))
            await entry.cycle(pending=req.rob)
        while not entry.observed.bus.valid:
            await entry.cycle()
        await entry.idle(rng.randrange(6))
        if rng.random() < 0.15:
            await entry.cycle(redirect=Redirect(True, req.rob, True))
            await reuse_and_complete(entry, nc=not nc, tag=rank + 100)
            continue
        await entry.issue()
        await entry.cycle(id_response=IdResponse(True, entry.spec["entry_id"], rng.randrange(16)))
        await entry.idle(rng.randrange(7))
        cancel = rng.random() < 0.2
        if cancel:
            await entry.cycle(redirect=Redirect(True, req.rob, True))
            await entry.idle(rng.randrange(1, 5))
        await entry.cycle(response=Response(True, rng.randrange(1 << 64), bool(rng.randrange(2)), bool(rng.randrange(2))))
        if cancel:
            await reuse_and_complete(entry, nc=not nc, tag=rank + 200)
            continue
        if entry.spec["wakeup_backpressure"]:
            await entry.idle(rng.randrange(6), mmio_wake_ready=False, nc_wake_ready=False)
        await entry.cycle()
        await entry.idle(rng.randrange(6))
        await entry.complete()
    assert entry.model.owner is None
