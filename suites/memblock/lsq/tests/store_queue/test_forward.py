from dataclasses import replace

import pytest

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.directed import scalar_word
from lsqverify.psq.types import Address, Attributes, Data
from lsqverify.raw.types import SqPtr
from lsqverify.store_queue.actor import StoreActor
from lsqverify.store_queue.directed import consume
from lsqverify.vlq.types import RobPtr
from lsqverify.vsq.types import Dispatch
from .helpers import requests


async def cross_store(env, *, alias):
    await env.cycle(dispatch=requests({0: (10, 1), 7: (11, 1)}) if alias else requests({0: (10, 1)}))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    young = Address(True, int(alias), 6, 0x2000C if alias else 0x1000C, 0xABC00C, 3, unaligned=True, cross_word=True, last=False)
    old = Address(True, 0, 4, 0x10010, 0xABC010, 2)
    await env.cycle(addresses=(old, young) if alias else (young, Address()),
                    data=(Data(True, 0, 4, 0x11111111), Data(True, 1, 6, 0x2222222222222222)) if alias else (Data(True, 0, 6, 0x8877665544332211), Data()))
    tail = replace(young, vaddr=young.vaddr // 16 * 16 + 16, paddr=0xABC010, last=True)
    await env.cycle(addresses=(Address(), tail) if alias else (tail, Address()), data=(Data(), Data()),
                    attributes=(Attributes(), Attributes(last=False)) if alias else (Attributes(last=False), Attributes()))
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()))
    await env.idle(3)


@pytest.mark.parametrize("lane", range(3))
async def test_cross_word_va_alias_latest_pa_bytes_through_true_parent(sq, lane):
    env = sq
    await cross_store(env, alias=True)
    env.begin(("SQ-FORWARD.alias",))
    queries, translations = [Query()] * 3, [Translation()] * 3
    queries[lane], translations[lane] = Query(True, 0x10010, SqPtr.encode(2), 2), Translation(0xABC010)
    await env.cycle(queries=tuple(queries))
    await env.cycle(queries=(Query(),) * 3, translations=tuple(translations))
    await consume(env, [(0x10010, 0xABC010, 15, 0x11111111), (0x20000, 0xABC000, 0xF000, 0x22222222 << 96),
                        (0x20010, 0xABC010, 15, 0x22222222)], 2, credits=2, rob_head=RobPtr.encode(12))
    env.finish(("SQ-FORWARD.alias",))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("word", (0, 1))
async def test_cross_word_store_cannot_supply_unwritten_pa_bytes(sq, lane, word):
    env = sq
    await cross_store(env, alias=False)
    env.begin(("SQ-FORWARD.range",))
    queries, translations = [Query()] * 3, [Translation()] * 3
    queries[lane], translations[lane] = Query(True, 0x10000 + word * 16, SqPtr.encode(1), 4), Translation(0xABC000 + word * 16)
    await env.cycle(queries=tuple(queries))
    await env.cycle(queries=(Query(),) * 3, translations=tuple(translations))
    await consume(env, [(0x10000, 0xABC000, 0xF000, 0x44332211 << 96), (0x10010, 0xABC010, 15, 0x88776655)], 1, credits=1, rob_head=RobPtr.encode(11))
    env.finish(("SQ-FORWARD.range",))


async def test_nonzero_head_low_age_group_all_lanes_then_real_drain(sq):
    actor = StoreActor(sq, seed=0x6501)
    for _ in range(60):
        actor.add()
    await actor.drain()
    active = [actor.add() for _ in range(64)]
    for _ in range(150):
        await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False))
        if all(actor.all[uid].s2_done and actor.all[uid].data_sent for item in active for uid in item.flows):
            break
    assert all(actor.all[uid].s2_done and actor.all[uid].data_sent for item in active for uid in item.flows)
    owner = actor.all[active[-1].flows[0]]
    await actor.step(issue=False, dispatch=False, advance_rob=False, sbuffer_ready=(False, False), queries=(Query(True, owner.address.vaddr, SqPtr.encode(124), 3),) * 3)
    await actor.step(issue=False, dispatch=False, advance_rob=False, sbuffer_ready=(False, False), queries=(Query(),) * 3, translations=(Translation(owner.address.paddr),) * 3)
    sq.expect({f"io_forward_{lane}_s2Resp_valid": 1 for lane in range(3)}, "actual SQ123/slot59 low-domain candidate reaches every real forward lane")
    await actor.drain()
    actor.checked(("SQ-FORWARD.data", "SQ-READY.upper"), [uid for item in active for uid in item.flows])


@pytest.mark.parametrize("lane", range(3))
async def test_clipped_dependency_preserves_actual_store_sq_generation(sq, lane):
    actor = StoreActor(sq, seed=0x6502)
    for _ in range(60):
        actor.add()
    await actor.drain()
    env = sq
    env.begin(("SQ-FORWARD.clipped",))
    await env.cycle(dispatch=requests({0: (70, 16), 1: (71, 16), 2: (72, 16), 3: (73, 16), 7: (74, 4)}, start=60))
    await env.cycle(dispatch=(Dispatch(),) * 8, addresses=(Address(True, 48, 6, 0x512000, 0xB12000, 3), Address()))
    await env.cycle(addresses=(Address(), Address()))
    await env.idle(4)
    queries, translations = [Query()] * 3, [Translation()] * 3
    queries[lane], translations[lane] = Query(True, 0x512000, SqPtr.encode(128), 3), Translation(0xB12000)
    await env.cycle(queries=tuple(queries))
    await env.cycle(queries=(Query(),) * 3, translations=tuple(translations))
    # This failed query must not be credited by an unrelated successful case.
    env.finish(("SQ-FORWARD.clipped",))
