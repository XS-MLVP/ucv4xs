from dataclasses import asdict, replace
import random

import pytest

from lsqverify.raw.types import SqPtr
from lsqverify.unalign.types import Inputs, Recovery, Request, canceled, encode, serial


@pytest.mark.parametrize("lane", (0, 1))
@pytest.mark.parametrize("field", ("first_flag", "second_flag"))
async def test_address_ready_full_flags_not_just_physical_value(unalign, lane, field):
    env = unalign
    req = env.request(sq=63)
    wrong = replace(req.sq, **{"first" if field == "first_flag" else "second": True})
    await env.cycle({lane: req}, address_ready=wrong)
    await env.idle(3)
    assert not env.last_change["accepted"] and not env.observed["io_toDeqModule_valid"]
    await env.enqueue(req, lane=lane)
    env.arm("UQ-ADMIT." + field)
    await env.drain()


@pytest.mark.parametrize("first_lane", (0, 1))
async def test_two_valid_inputs_only_current_addr_ready_identity_fires(unalign, first_lane):
    env = unalign
    first, second = env.request(14), env.request(17, page=0x123456789)
    change = await env.cycle({first_lane: first, 1 - first_lane: second}, address_ready=first.sq)
    assert len(change["accepted"]) == 1 and change["accepted"][0]["input_lane"] == first_lane
    await env.enqueue(second, lane=1 - first_lane)
    env.arm(("UQ-ADMIT.multiple_valid", "UQ-CAPACITY.two", "UQ-ORDER.gaps", "UQ-FORWARD.different_pages"))
    assert env.observed["io_forwardValid_0"] and env.observed["io_forwardValid_1"]
    await env.drain()


async def test_full_stalls_even_when_head_consumes_in_same_cycle(unalign):
    env = unalign
    await env.enqueue(env.request(7))
    await env.enqueue(env.request(8), lane=1)
    old = [asdict(x) for x in env.model.order]
    pending = env.request(9, page=0xF00000001)
    for _ in range(4):
        change = await env.enqueue(pending)
        assert not change["accepted"] and not env.pre_observed["io_fromStaS1_0_ready"]
    env.arm(("UQ-CAPACITY.full", "UQ-CAPACITY.two"), old)
    change = await env.enqueue(pending, ready=True)
    assert len(change["consumed"]) == 1 and not change["accepted"]
    await env.enqueue(pending, lane=1)
    env.arm("UQ-CAPACITY.no_same_cycle_reuse", old + env.last_change["accepted"])
    await env.drain()


@pytest.mark.parametrize("same_page", (False, True))
async def test_forward_slots_keep_complete_sq_with_equal_or_distinct_page(unalign, same_page):
    env = unalign
    await env.enqueue(env.request(127, page=0xA23456789), lane=1)
    await env.enqueue(env.request(130, page=0xA23456789 if same_page else 0x123456789), lane=0)
    env.arm("UQ-FORWARD.same_page" if same_page else "UQ-FORWARD.different_pages")
    await env.idle(6)
    await env.drain()


@pytest.mark.parametrize("lane", (0, 1))
async def test_complete_page_bits_and_input_offsets_are_checked_on_consumption(unalign, lane):
    env = unalign
    sq = 1
    for bit in range(36):
        for complement in (False, True):
            page = (1 << bit) ^ (((1 << 36) - 1) if complement else 0)
            req = env.request(sq, page=page, offset=4095 if complement else 0)
            await env.enqueue(req, lane=lane)
            env.arm(("UQ-PAGE.bits", "UQ-PAGE.offset"))
            await env.drain()
            sq += 1
    for offset in (0, 4095, *(1 << bit for bit in range(12)), *(4095 ^ (1 << bit) for bit in range(12))):
        await env.enqueue(env.request(sq, page=0xF12345678, offset=offset), lane=lane)
        env.arm("UQ-PAGE.offset")
        await env.drain()
        sq += 1


async def test_four_sq_flag_regions_and_many_two_slot_ring_wraps(unalign):
    env = unalign
    owners = []
    for sq in range(512):
        change = await env.enqueue(env.request(sq, page=(0x123450000 + sq) & ((1 << 36) - 1)), lane=sq % 2)
        owners.extend(change["accepted"])
        await env.drain()
    env.arm(("UQ-ORDER.wrap", "UQ-REUSE.consume"), owners)
    await env.idle(1)


@pytest.mark.parametrize("kind", ("none", "equal", "younger", "all", "repeated"))
@pytest.mark.parametrize("odd_tail", (False, True))
async def test_recovery_cancels_suffix_then_same_slots_finish_new_identity(unalign, kind, odd_tail):
    env = unalign
    if odd_tail:
        await env.enqueue(env.request(4))
        await env.drain()
    await env.enqueue(env.request(10))
    await env.enqueue(env.request(13, page=0x123456789), lane=1)
    old = [asdict(x) for x in env.model.order]
    cutoff = {"none": 14, "equal": 13, "younger": 12, "all": 10, "repeated": 13}[kind]
    pending = env.request(15, page=0x876543210)
    change = await env.enqueue(pending, redirect=Recovery(True, SqPtr.encode(cutoff)))
    assert not change["accepted"] and env.pre_observed["io_toDeqModule_valid"]
    if not change["canceled"]:
        env.arm(("UQ-REDIRECT.none", "UQ-REDIRECT.block_enqueue"), old)
        await env.drain()
        return
    canceled_owners = change["canceled"]
    names = ["UQ-REDIRECT.block_enqueue", "UQ-REUSE.cancel", "UQ-REUSE.rollback"]
    if kind in ("equal", "all", "repeated"):
        names.append("UQ-REDIRECT.equal")
    if kind == "all":
        assert len(canceled_owners) == 2
        names.append("UQ-REDIRECT.all")
    else:
        assert len(canceled_owners) == 1
        names.extend(("UQ-REDIRECT.last", "UQ-REDIRECT.younger"))
    env.arm(names, canceled_owners, reuse=True)
    if kind == "repeated":
        env.arm("UQ-REDIRECT.repeated", canceled_owners, reuse=True)
        for _ in range(3):
            change = await env.cycle(redirect=Recovery(True, SqPtr.encode(cutoff)))
            assert not change["canceled"]
    await env.enqueue(pending, lane=1)
    if kind == "all":
        await env.enqueue(env.request(16, page=0xAAAAAAAAA), lane=0)
    await env.drain()


@pytest.mark.parametrize("base", (0, 63, 64, 127, 128, 191, 192, 255))
async def test_recovery_uses_full_sq_age_across_every_flag_boundary(unalign, base):
    env = unalign
    await env.enqueue(env.request(base))
    await env.enqueue(env.request(base + 3, page=0x100000001), lane=1)
    change = await env.cycle(redirect=Recovery(True, SqPtr.encode(base + 1)))
    assert len(change["canceled"]) == 1 and len(env.model.order) == 1
    env.arm("UQ-REDIRECT.flags", change["canceled"], reuse=True)
    await env.enqueue(env.request(base + 5, page=0xE00000001), lane=0)
    await env.drain()


async def test_committed_head_consumption_overlaps_recovery_of_younger_tail(unalign):
    env = unalign
    await env.enqueue(env.request(10))
    await env.enqueue(env.request(13), lane=1)
    pending = env.request(15, page=0x555555555)
    change = await env.enqueue(pending, ready=True, redirect=Recovery(True, SqPtr.encode(13)))
    assert len(change["consumed"]) == len(change["canceled"]) == 1 and not change["accepted"]
    assert not env.observed["io_toDeqModule_valid"]
    env.arm("UQ-REDIRECT.consume_survivor", change["canceled"], reuse=True)
    await env.enqueue(pending, lane=1)
    await env.drain()


@pytest.mark.parametrize("phase", ("one_live", "two_live", "wrapped"))
async def test_reset_aborts_old_second_pages_then_new_uid_completes(unalign, phase):
    env = unalign
    if phase == "wrapped":
        await env.enqueue(env.request(1))
        await env.drain()
    await env.enqueue(env.request(7))
    if phase == "two_live":
        await env.enqueue(env.request(9), lane=1)
    await env.idle(4)
    await env.reset()
    await env.enqueue(env.request(15, page=0x123456789), lane=1)
    env.arm("UQ-RESET." + phase)
    await env.drain()


async def test_disabled_payload_does_not_modify_head_or_forward(unalign):
    env = unalign
    await env.enqueue(env.request(7))
    env.arm("UQ-IDLE.disabled")
    for i in range(12):
        req = replace(env.request(100 + i, page=1 << i), valid=False)
        await env.cycle({i % 2: req}, address_ready=req.sq)
    await env.drain()


async def test_domain_rejections_are_not_dynamic_hardware_proofs(unalign):
    env = unalign
    for inp in (Inputs(requests=(Request(),)), Inputs((env.request(page=1 << 36), Request())),
                Inputs(address_ready=SqPtr(False, False, 64))):
        with pytest.raises(ValueError):
            encode(inp)
    req = env.request(7)
    with pytest.raises(ValueError):
        env.model.validate(Inputs((req, req), req.sq))
    await env.enqueue(req)
    with pytest.raises(ValueError):
        env.model.validate(Inputs(ready=True, redirect=Recovery(True, req.sq)))
    with pytest.raises(ValueError):
        env.model.validate(Inputs((env.request(135), Request()), SqPtr.encode(135)))
    await env.drain()


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_ordered_cross_page_requests_and_recoveries(unalign, seed):
    env = unalign
    rng, cursor, owners, canceled_owners = random.Random(seed), 0, [], []
    for _ in range(1200):
        live = list(env.model.order)
        recovery = Recovery()
        if rng.random() < 0.16:
            if live:
                cutoff = serial(rng.choice(live).request.sq) + rng.choice((0, 1))
            else:
                cutoff = cursor
            recovery = Recovery(True, SqPtr.encode(cutoff))
        ready = rng.random() < 0.55
        if live and canceled(live[0].request.sq, recovery):
            ready = False
        reqs = {}
        lane = rng.randrange(2)
        req = env.request(cursor, page=rng.getrandbits(36), offset=rng.randrange(4096))
        if rng.random() < 0.8:
            reqs[lane] = req
        if rng.random() < 0.25:
            reqs[1 - lane] = env.request(cursor + 1, page=rng.getrandbits(36))
        change = await env.cycle(reqs, address_ready=req.sq, ready=ready, redirect=recovery)
        owners.extend(change["accepted"])
        if change["accepted"]:
            cursor += rng.randrange(1, 4)
        if recovery.valid:
            cursor = serial(recovery.sq)
        if change["canceled"]:
            canceled_owners.extend(change["canceled"])
            env.arm("UQ-REUSE.cancel", change["canceled"], reuse=True)
    positive = [owner for owner in owners if owner["uid"] not in env.coverage.canceled]
    env.arm("UQ-CONCURRENT.seeded", positive)
    await env.drain()
    # Finish at least one fresh UID in each physical slot after the last
    # recovery, so every canceled-slot reuse proof has a real completion.
    await env.enqueue(env.request(cursor, page=0x123456789))
    await env.enqueue(env.request(cursor + 1, page=0xA23456789), lane=1)
    await env.drain()
