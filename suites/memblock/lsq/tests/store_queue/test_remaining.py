
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.checks import check_word, ptr_values, read_ptr
from suites.memblock.lsq.psq.directed import scalar_word
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_queue.directed import consume
from suites.memblock.lsq.vlq.types import Redirect, RobPtr
from suites.memblock.lsq.vsq.types import Dispatch
from .helpers import finish_special, pair, requests, wait_valid, write


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
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 0), **ptr_values(P.p_toLoadQueue_stDataReadySqPtr_, 1),
                P.p_toLoadQueue_stAddrReadyVec_1: 1, P.p_toLoadQueue_stAddrReadyVec_2: 1, P.p_toLoadQueue_stDataReadyVec_2: 1}, "independent continuous prefixes cannot jump their actual holes")
    await env.cycle(addresses=(replace(owners[0][0], tlb_miss=True), Address()))
    await env.cycle(addresses=(Address(), Address()))
    await env.idle(3)
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 0), P.p_toLoadQueue_stAddrReadyVec_0: 0}, "TLB miss does not close the address prefix")
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
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_dataInvalid_valid"): 1 for lane in range(3)}, "missing newest data must block old-value success")
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_dataInvalid_bits_value"): 1 for lane in range(3)}, "dependency keeps actual SQ1 owner")
    await env.cycle(data=(d1, Data()))
    await env.cycle(data=(Data(), Data()))
    await query(env, a1, 2)
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_forwardData_{byte}"): 0x22 for lane in range(3) for byte in range(8)}, "newest original data wins after real STD arrival")
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
    await wait_valid(env, P.p_writeToSbuffer_req_0_valid)
    await env.cycle(sbuffer_ready=(True, True), queries=(Query(True, address.vaddr, SqPtr.encode(1), 3),) * 3)
    check_word(env, 0, *scalar_word(address, data), before=True)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr), Translation(address.paddr, True), Translation(address.paddr)))
    env.expect({P.io(f"forward_{lane}_s2Resp_valid"): int(lane != 1) for lane in range(3)}, "only killed S0 owner is cancelled while peer queries accepted at real consumption still respond")
    await env.idle(8, translations=(Translation(),) * 3)
    env.expect({P.p_sqEmpty: 1, **ptr_values(P.p_sqDeqPtr_, 1)}, "real physical credit and virtual feedback have completed")
    await query(env, address, 1)
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_forwardMask_{byte}"): 0 for lane in range(3) for byte in range(16)}, "new queries after release cannot see old slot data")
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
        if env.observed[P.p_toLsqEnqCtrl_sqRedirectPtr_valid]:
            env.expect(ptr_values(P.p_toLsqEnqCtrl_sqRedirectPtr_bits_, 1), "true VSQ recovers exclusive tail from surviving dispatch")
            seen = True
    assert seen and not env.observed[P.p_toLsqEnqCtrl_sqRecoverStall]
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
            await wait_valid(env, P.p_writeToSbuffer_req_0_valid)
            await env.cycle(sbuffer_ready=(True, True))
            check_word(env, 0, va, pa, 255, 0, wline=1, before=True)
            await wait_valid(env, P.p_writeBack_valid)
        else:
            await wait_valid(env, P.p_toDCache_req_valid)
            env.expect({P.p_toDCache_req_bits_opcode: cbo, P.p_toDCache_req_bits_address: pa}, "slot/lane-specific actual CBO request")
            await env.cycle(cache_ready=True)
            await env.cycle(cache_response=True)
        await env.cycle(cache_response=False, writeback_ready=True)
        env.expect({P.p_writeBack_valid: 1, P.p_writeBack_bits_robIdx_value: rob.value}, "each slot/lane CBO owner has actual WB fire", before=True)
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
    await wait_valid(env, P.p_writeToSbuffer_req_1_valid)
    await env.idle(hold)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x94000, 0xABCD000, 0xF000, 0x44332211 << 96, before=True)
    check_word(env, 1, 0x94010, 0xABCD010, 15, 0x88776655, before=True)
    await wait_valid(env, P.p_toDCache_req_valid)
    await env.cycle(cache_ready=True)
    await env.cycle(cache_response=True)
    await env.cycle(cache_response=False, writeback_ready=True)
    env.expect({P.p_writeBack_valid: 1, P.p_writeBack_bits_robIdx_value: 11}, "nonzero neighbor control also really completes", before=True)
    await finish_special(env, 2)
    env.finish(names)
