
from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.env.directed import scalar_word
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.env.directed import consume
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import cache
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import check_word
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import finish_special
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import forward
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import observation
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import word
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import writeback
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import rob as ident
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import pair
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import requests
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import wait_valid
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import write


async def query(env, address, end, *, kill=(False, False, False)):
    await env.cycle(queries=(Query(True, address.vaddr, SqPtr.encode(end), address.size),) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=tuple(Translation(address.paddr, flag) for flag in kill))


async def test_ready_holes_and_tlb_retry_do_not_advance_unready_prefix(sq):
    env = sq
    names = ("SQ-READY.holes", "SQ-READY.retry")
    env.begin(names)
    owners = [(Address(True, i, 6, 0x100000 + i * 4096, 0xA000000 + i * 4096, 3), Data(True, i, 6, 0x8877665544332200 + i)) for i in range(3)]
    await env.cycle(dispatch=requests({6: (10, 3)}))
    await env.cycle(dispatch=(Dispatch(),) * 8, addresses=(owners[2][0], owners[1][0]), data=(owners[0][1], owners[2][1]))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    env.expect(observation(addr_ready_ptr=sqptr(0), data_ready_ptr=sqptr(1),
                           addr_ready_mask=0b110, data_ready_mask=0b100),
               "independent continuous prefixes cannot jump their actual holes")
    await env.cycle(addresses=(replace(owners[0][0], tlb_miss=True), Address()))
    await env.cycle(addresses=(Address(), Address()))
    await env.idle(3)
    env.expect(observation(addr_ready_ptr=sqptr(0), addr_ready_clear_mask=1), "TLB miss does not close the address prefix")
    await env.cycle(addresses=(owners[0][0], Address()), data=(owners[1][1], Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await consume(env, [scalar_word(*item) for item in owners], 3, rob_head=RobPtr.encode(11))
    env.finish(names)


async def test_youngest_missing_data_dependency_then_newest_bytes(sq):
    env = sq
    names = ("SQ-FORWARD.wait", "SQ-FORWARD.youngest")
    env.begin(names)
    a0, a1 = Address(True, 0, 6, 0x300000, 0xB000000, 3), Address(True, 1, 6, 0x300000, 0xB000000, 3)
    d0, d1 = Data(True, 0, 6, 0x1111111111111111), Data(True, 1, 6, 0x2222222222222222)
    await env.cycle(dispatch=requests({0: (10, 1), 7: (11, 1)}))
    await env.cycle(dispatch=(Dispatch(),) * 8, addresses=(a0, a1), data=(d0, Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    await query(env, a1, 2)
    env.expect(observation(forward=tuple(forward(valid=None, data_invalid=True) for _ in range(3))),
               "missing newest data must block old-value success")
    env.expect(observation(forward=tuple(forward(valid=None, data_invalid_value=1)
                                          for _ in range(3))),
               "dependency keeps actual SQ1 owner")
    await env.cycle(data=(d1, Data()))
    await env.cycle(data=(Data(), Data()))
    await query(env, a1, 2)
    env.expect(observation(forward=tuple(forward(valid=None, data_byte_mask=0x00FF,
                                                 forward_data=0x2222222222222222) for _ in range(3))),
               "newest original data wins after real STD arrival")
    await consume(env, [scalar_word(a0, d0), scalar_word(a1, d1)], 2, rob_head=RobPtr.encode(12))
    env.finish(names)


async def test_s1_kill_and_dequeue_visible_window_keep_exact_query_owner(sq):
    env = sq
    names = ("SQ-FORWARD.kill", "SQ-FORWARD.deq")
    env.begin(names)
    address, data = Address(True, 0, 6, 0x400000, 0xC000000, 3), Data(True, 0, 6, 0x8877665544332211)
    await env.cycle(dispatch=requests({4: (10, 1)}), rob_head=RobPtr.encode(10))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, address, data)
    await wait_valid(env, "sbuffer_word_0")
    await env.cycle(sbuffer_ready=(True, True), queries=(Query(True, address.vaddr, SqPtr.encode(1), 3),) * 3)
    check_word(env, 0, *scalar_word(address, data), before=True)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr), Translation(address.paddr, True), Translation(address.paddr)))
    env.expect(observation(forward=tuple(forward(valid=int(lane != 1)) for lane in range(3))),
               "only killed S0 owner is cancelled while peer queries accepted at real consumption still respond")
    await env.idle(8, translations=(Translation(),) * 3)
    env.expect(observation(empty=1, sq_deq_ptr=sqptr(1)), "real physical credit and virtual feedback have completed")
    await query(env, address, 1)
    env.expect(observation(forward=tuple(forward(valid=None, forward_mask=0) for _ in range(3))),
               "new queries after release cannot see old slot data")
    env.finish(names)


async def test_legal_previous_dispatch_inflight_recovery_then_new_slot_data(sq):
    env = sq
    names = ("SQ-RECOVER.inflight", "SQ-REUSE.cancelled")
    env.begin(names)
    old = Address(True, 0, 6, 0x500000, 0xA000000, 3), Data(True, 0, 6, 0x1111111111111111)
    await env.cycle(dispatch=requests({0: (10, 1)}))
    await env.cycle(dispatch=requests({7: (11, 1)}, start=1), addresses=(old[0], Address()), data=(old[1], Data()))
    await env.cycle(dispatch=(Dispatch(),) * 8, redirect=Redirect(True, RobPtr.encode(10)),
                    addresses=(Address(True, 1, 6, 0x600000, 0xB000000, 3), Address()), data=(Data(True, 1, 6, 0x2222222222222222), Data()))
    await env.cycle(redirect=Redirect(), addresses=(Address(), Address()), data=(Data(), Data()), attributes=(Attributes(exception=True), Attributes()))
    seen = False
    for _ in range(14):
        await env.cycle(attributes=(Attributes(), Attributes()))
        if env.response.redirect_valid:
            env.expect(observation(redirect_ptr=sqptr(1)), "true VSQ recovers exclusive tail from surviving dispatch")
            seen = True
    assert seen and not env.response.recover_stall
    new = Address(True, 1, 6, 0x800000, 0xE000000, 3), Data(True, 1, 6, 0xEEEEDDCCBBAA9988)
    await env.cycle(dispatch=requests({4: (11, 1)}, start=1))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, *new, lane=1)
    await consume(env, [scalar_word(*old), scalar_word(*new)], 2, rob_head=RobPtr.encode(12))
    env.finish(names)


async def test_all_cbo_slots_both_sta_lanes_actual_complete(sq):
    env = sq
    names = ("SQ-SPECIAL.cbo", "SQ-WRITE.slots", "SQ-DISPATCH.lanes")
    env.begin(names)
    for position in range(128):
        cbo, lane, rob = position % 4, position // 64, RobPtr.encode(10 + position, former=bool(position % 2))
        va, pa, op = 0x100000 + position * 4096, 0xA000000 + position * 4096, cbo * 2 + 1
        await env.cycle(dispatch=requests({position % 8: (rob, 1)}, start=position), rob_head=rob,
                        sbuffer_ready=(False, False), cache_ready=False, cache_response=False, writeback_ready=False)
        await env.cycle(dispatch=(Dispatch(),) * 8)
        await write(env, Address(True, position % 64, op, va, pa, 3), Data(True, position % 64, op, 0x8877665544332211 + position), lane=lane)
        if cbo == 3:
            await wait_valid(env, "sbuffer_word_0")
            await env.cycle(sbuffer_ready=(True, True))
            check_word(env, 0, va, pa, 255, 0, wline=1, before=True)
            await wait_valid(env, "writeback")
        else:
            await wait_valid(env, "cache_request")
            env.expect(observation(cache_request=cache(address=pa, opcode=cbo, valid=None)), "slot/lane-specific actual CBO request")
            await env.cycle(cache_ready=True)
            await env.cycle(cache_response=True)
        await env.cycle(cache_response=False, writeback_ready=True)
        env.expect(observation(writeback=writeback(rob_identity=ident(rob.value))),
                   "each slot/lane CBO owner has actual WB fire", before=True)
        await finish_special(env, position + 1)
    env.finish(names)


@pytest.mark.parametrize("sq", (False,), indirect=True)
@pytest.mark.parametrize("neighbor", range(4))
@pytest.mark.parametrize("hold", (0, 3))
async def test_retired_split_then_rob_head_cbo_tail_fire_keeps_ordinary_control(sq, neighbor, hold):
    env = sq
    names = ("SQ-SPECIAL.split_wline",) if neighbor == 3 else ("SQ-WRITE.line",)
    env.begin(names)
    first = Address(True, 0, 6, 0x9400C, 0xABCD00C, 3, unaligned=True, cross_word=True, last=False)
    await env.cycle(dispatch=requests({0: (10, 1), 7: (11, 1)}))
    await env.cycle(dispatch=(Dispatch(),) * 8, addresses=(first, Address()), data=(Data(True, 0, 6, 0x8877665544332211), Data()))
    await env.cycle(addresses=(replace(first, vaddr=0x94010, paddr=0xABCD010, last=True), Address()), data=(Data(), Data()), attributes=(Attributes(last=False), Attributes()))
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()))
    await env.idle(3)
    # The ordinary store is fully executed BEFORE ROB advances to CBO.
    op = neighbor * 2 + 1
    await env.cycle(rob_head=RobPtr.encode(11), addresses=(Address(True, 1, op, 0xA0000, 0xC000000, 3), Address()), data=(Data(True, 1, op, 0), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await wait_valid(env, "sbuffer_word_1")
    await env.idle(hold)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x94000, 0xABCD000, 0xF000, 0x44332211 << 96, before=True)
    check_word(env, 1, 0x94010, 0xABCD010, 15, 0x88776655, before=True)
    await wait_valid(env, "cache_request")
    await env.cycle(cache_ready=True)
    await env.cycle(cache_response=True)
    await env.cycle(cache_response=False, writeback_ready=True)
    env.expect(observation(writeback=writeback(rob_identity=ident(11))),
               "nonzero neighbor control also really completes", before=True)
    await finish_special(env, 2)
    env.finish(names)
