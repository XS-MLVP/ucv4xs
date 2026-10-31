
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.psq.checks import check_word, ptr_values
from suites.memblock.lsq.psq.directed import scalar_word
from suites.memblock.lsq.psq.types import Address, Attributes, Data, SecondPage
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_queue.actor import StoreActor
from suites.memblock.lsq.store_queue.directed import consume
from suites.memblock.lsq.vlq.types import RobPtr
from suites.memblock.lsq.vsq.types import Dispatch
from .helpers import pair, requests


@pytest.mark.parametrize("size", range(5))
async def test_all_byte_offsets_through_real_vsq_psq_and_both_queues_drain(sq, size):
    actor = StoreActor(sq, seed=0x6400 + size)
    uids = []
    for offset in range(16):
        uids.extend(actor.add(size=size, offset=offset).flows)
    await actor.drain()
    actor.checked(("SQ-WRITE.sizes", "SQ-WRITE.word", "SQ-CREDIT.split") if size > 0 else ("SQ-WRITE.sizes",), uids)


@pytest.mark.parametrize("page", (False, True))
async def test_real_second_page_or_line_split_partial_consumption_credit(sq, page):
    env = sq
    names = ("SQ-WRITE.word", "SQ-WRITE.line", "SQ-CREDIT.split") + (("SQ-WRITE.page",) if page else ())
    env.begin(names)
    va, pa = (0x20FFC, 0xABCDFFC) if page else (0x2003C, 0xABCD03C)
    second = 0xD000000 if page else pa // 16 * 16 + 16
    first = Address(True, 0, 6, va, pa, 3, unaligned=True, cross_word=True, last=False)
    await env.cycle(dispatch=requests({7: (10, 1)}), rob_head=RobPtr.encode(10))
    await env.cycle(dispatch=(Dispatch(),) * 8, addresses=pair(first, 1), data=(Data(True, 0, 6, 0x8877665544332211), Data()),
                    second_pages=pair(SecondPage(True, SqPtr(), second), 0) if page else (SecondPage(),) * 2)
    if page:
        env.expect({P.p_fromStoreUnit_unalignQueueReq_0_ready: 1}, "actual integrated UQ accepts the second physical page", before=True)
    await env.cycle(addresses=pair(replace(first, vaddr=va + 4, paddr=second, last=True), 1), data=(Data(), Data()),
                    attributes=pair(Attributes(last=False), 1), second_pages=(SecondPage(),) * 2)
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(),) * 2)
    from .helpers import wait_valid
    await wait_valid(env, P.p_writeToSbuffer_req_1_valid)
    check_word(env, 0, va // 16 * 16, pa // 16 * 16, 0xF000, 0x44332211 << 96)
    check_word(env, 1, va // 16 * 16 + 16, second, 0xF, 0x88776655)
    await env.cycle(sbuffer_ready=(True, False))
    env.expect({**ptr_values(P.p_sqDeqPtr_, 0), P.p_toLsqEnqCtrl_sqDeq_valid: 0, P.p_sqEmpty: 0}, "only first segment consumed, original virtual/physical owner remains live")
    await consume(env, [(va // 16 * 16 + 16, second, 0xF, 0x88776655)], 1, credits=1)
    env.finish(names)


async def test_dispatch_filter_and_zero_flow_no_phantom_side_effect(sq):
    env = sq
    names = ("SQ-DISPATCH.filter", "SQ-DISPATCH.zero", "SQ-DISPATCH.sparse", "SQ-DISPATCH.multi")
    env.begin(names)
    dispatch = list(requests({0: (10, 0), 7: (12, 2)}))
    dispatch[3] = Dispatch(True, False, RobPtr.encode(11), 16, SqPtr.encode(99))
    dispatch[5] = Dispatch(False, True, RobPtr.encode(11), 16, SqPtr.encode(99))
    await env.cycle(dispatch=tuple(dispatch))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    owners = [(Address(True, i, 6, 0x50000 + i * 4096, 0xABC000 + i * 4096, 3), Data(True, i, 6, 0x8877665544332200 + i)) for i in range(2)]
    await env.cycle(addresses=tuple(item[0] for item in owners), data=tuple(item[1] for item in owners))
    await env.cycle(addresses=(Address(),) * 2, data=(Data(),) * 2)
    await consume(env, [scalar_word(*item) for item in owners], 2, rob_head=RobPtr.encode(13))
    env.finish(names)
