from dataclasses import replace

import pytest

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.psq.directed import consume_writes
from suites.memblock.lsq.raw.types import SqPtr


async def cross_store(env, *, alias):
    young = Address(True, int(alias), 6, 0x2000C if alias else 0x1000C, 0xABC00C, 3, unaligned=True, cross_word=True, last=False)
    old = Address(True, 0, 4, 0x10010, 0xABC010, 2)
    addresses = (old, young) if alias else (young, Address())
    data = (Data(True, 0, 4, 0x11111111), Data(True, 1, 6, 0x2222222222222222)) if alias else (Data(True, 0, 6, 0x8877665544332211), Data())
    await env.cycle(enqueue=SqPtr.encode(2 if alias else 1), addresses=addresses, data=data)
    tail = replace(young, vaddr=young.vaddr // 16 * 16 + 16, paddr=0xABC010, last=True)
    await env.cycle(addresses=(Address(), tail) if alias else (tail, Address()), data=(Data(), Data()),
                    attributes=(Attributes(), Attributes(last=False)) if alias else (Attributes(last=False), Attributes()))
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()))
    await env.idle(3)


@pytest.mark.parametrize("lane", range(3))
async def test_real_parent_cross_word_va_alias_never_returns_old_pa_bytes(psq_full, lane):
    env = psq_full
    await cross_store(env, alias=True)
    env.begin(("PSQ-FORWARD.alias",))
    queries, translations = [Query()] * 3, [Translation()] * 3
    queries[lane], translations[lane] = Query(True, 0x10010, SqPtr.encode(2), 2), Translation(0xABC010)
    await env.cycle(queries=tuple(queries))
    # The independent physical-byte safety oracle must reject an old value
    # with no replay, even when the detailed VA overlap reference agrees.
    await env.cycle(queries=(Query(),) * 3, translations=tuple(translations))
    await consume_writes(env, [(0x10010, 0xABC010, 0xF, 0x11111111), (0x20000, 0xABC000, 0xF000, 0x22222222 << 96),
                               (0x20010, 0xABC010, 0xF, 0x22222222)], 2, credits=2, retired=SqPtr.encode(2))
    env.finish(("PSQ-FORWARD.alias",))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("word", (0, 1))
async def test_real_parent_cross_word_mask_cannot_name_unwritten_pa_bytes(psq_full, lane, word):
    env = psq_full
    await cross_store(env, alias=False)
    env.begin(("PSQ-FORWARD.range",))
    queries, translations = [Query()] * 3, [Translation()] * 3
    queries[lane] = Query(True, 0x10000 + word * 16, SqPtr.encode(1), 4)
    translations[lane] = Translation(0xABC000 + word * 16)
    await env.cycle(queries=tuple(queries))
    await env.cycle(queries=(Query(),) * 3, translations=tuple(translations))
    await consume_writes(env, [(0x10000, 0xABC000, 0xF000, 0x44332211 << 96), (0x10010, 0xABC010, 0xF, 0x88776655)],
                         1, credits=1, retired=SqPtr.encode(1))
    env.finish(("PSQ-FORWARD.range",))
