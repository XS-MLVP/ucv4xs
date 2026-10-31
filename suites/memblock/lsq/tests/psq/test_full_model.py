
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.psq.actor import PsqActor
from suites.memblock.lsq.raw.types import SqPtr


@pytest.mark.parametrize("order", ("address", "data", "together"))
async def test_staged_reference_calibration_real_write_query_and_dequeue(psq_full, order):
    env = psq_full
    address, data = Address(True, 0, 6, 0x10008, 0xABC008, 3), Data(True, 0, 6, 0x8877665544332211)
    await env.cycle(enqueue=SqPtr.encode(1), addresses=(address, Address()) if order != "data" else (Address(), Address()),
                    data=(data, Data()) if order != "address" else (Data(), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(4)
    await env.cycle(addresses=(address, Address()) if order == "data" else (Address(), Address()),
                    data=(data, Data()) if order == "address" else (Data(), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    await env.cycle(queries=(Query(True, address.vaddr, SqPtr.encode(1), 3),) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    await env.idle(12, retired=SqPtr.encode(1), sbuffer_ready=(True, True))
    assert env.observed[P.p_sqDeqPtr_value] == 1


async def test_staged_reference_split_and_redirect_calibration(psq_full):
    env = psq_full
    first = Address(True, 0, 6, 0x2000C, 0xABC00C, 3, unaligned=True, cross_word=True, last=False)
    await env.cycle(enqueue=SqPtr.encode(2), addresses=(first, Address()), data=(Data(True, 0, 6, 0x8877665544332211), Data()))
    await env.cycle(addresses=(replace(first, last=True), Address()), data=(Data(), Data()), attributes=(Attributes(last=False), Attributes()))
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()))
    await env.idle(3)
    await env.cycle(redirect_valid=True, redirect=SqPtr.encode(1), enqueue=SqPtr.encode(1))
    await env.cycle(redirect_valid=False)
    await env.idle(12, retired=SqPtr.encode(1), sbuffer_ready=(True, True))
    assert env.observed[P.p_sqDeqPtr_value] == 1


@pytest.mark.parametrize("seed", (0x5301, 0x5302, 0x5303))
async def test_full_reference_external_uid_actor_seeded_mix_and_drain(psq_full, seed):
    actor = PsqActor(psq_full, seed=seed)
    rng, uids, target = actor.rng, [], 300
    reached = False
    for _ in range(70):
        uids.append(actor.add(size=rng.randrange(5), offset=0))
    for _ in range(6000):
        for _ in range(rng.randrange(3)):
            if len(uids) == target or actor.tail - actor.head == 128:
                break
            choice = rng.randrange(10)
            if choice == 0:
                uid = actor.add(size=3, cbo=rng.randrange(4))
            elif choice < 3:
                size = rng.randrange(4)
                uid = actor.add(size=size, offset=rng.randrange(8 // (1 << size)) * (1 << size) + rng.choice((0, 8)), memory=rng.choice((1, 2, 7)))
            else:
                size = rng.randrange(5)
                page = size >= 3 and rng.random() < 0.15
                uid = actor.add(size=size, offset=rng.randrange(16), page=page, retry=rng.random() < 0.1)
            uids.append(uid)
        await actor.step(query=rng.random() < 0.5)
        if not reached and psq_full.last_change["sta_slots"] and psq_full.last_change["std_slots"]:
            psq_full.begin(("PSQ-CONCURRENT.seeded",))
            reached = True
        if len(uids) == target:
            break
    assert len(uids) == target
    await actor.drain()
    actor.checked(("PSQ-CONCURRENT.seeded",), uids)


@pytest.mark.parametrize("phase", ("queue", "response", "wb"))
async def test_full_reference_active_reset_new_uid_completes_same_slot(psq_full, phase):
    actor = PsqActor(psq_full)
    old = actor.add(cbo=1 if phase != "queue" else None)
    for _ in range(20):
        await actor.step(fair=True, sbuffer_ready=(False, False), cache_response=False, writeback_ready=False)
        if phase == "queue" and psq_full.observed[P.p_writeToSbuffer_req_0_valid]:
            break
        if phase != "queue" and psq_full.observed[P.p_toDCache_resp_ready]:
            break
    if phase == "queue":
        assert psq_full.observed[P.p_writeToSbuffer_req_0_valid]
    else:
        assert actor.pending is not None
        if phase == "wb":
            await actor.step(fair=True, writeback_ready=False)
            assert psq_full.observed[P.p_writeBack_valid]
    assert await actor.reset() == [old]
    new = actor.add(size=2)
    await actor.drain()
    assert old not in actor.completed and old in actor.aborted and new != old
    actor.checked(("PSQ-RESET.active",), [new])


@pytest.mark.parametrize("seed", (0x5401, 0x5402))
async def test_full_reference_controlled_nonzero_inwindow_mix_completes(psq_full, seed):
    """Necessary-condition control only; original full-domain failures remain."""
    actor = PsqActor(psq_full, seed=seed)
    rng, uids = actor.rng, []
    reached = False
    for _ in range(4000):
        for _ in range(rng.randrange(3)):
            if len(uids) == 300 or actor.tail - actor.head == 48:
                break
            choice = rng.randrange(10)
            if choice == 0:
                uid = actor.add(size=3, cbo=rng.randrange(3))
            elif choice < 3:
                size = rng.randrange(4)
                uid = actor.add(size=size, offset=rng.choice((0, 8)), memory=rng.choice((1, 2, 7)))
            else:
                size = rng.randrange(5)
                uid = actor.add(size=size, offset=rng.randrange(16), page=size >= 3 and rng.random() < 0.1, retry=rng.random() < 0.1)
            uids.append(uid)
        await actor.step(query=rng.random() < 0.5)
        if not reached and psq_full.last_change["sta_slots"] and psq_full.last_change["std_slots"]:
            psq_full.begin(("PSQ-CONCURRENT.controlled",))
            reached = True
        if len(uids) == 300:
            break
    assert len(uids) == 300
    await actor.drain()
    actor.checked(("PSQ-CONCURRENT.controlled",), uids)
