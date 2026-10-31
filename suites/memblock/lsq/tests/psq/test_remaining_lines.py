
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.checks import check_word, ptr_values
from suites.memblock.lsq.psq.directed import consume_writes, scalar_word
from suites.memblock.lsq.psq.types import Address, Attributes, Data, SecondPage
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


def pair(item, lane):
    return tuple(item if i == lane else type(item)() for i in range(2))


@pytest.mark.parametrize("lane", (0, 1))
@pytest.mark.parametrize("memory_type", (1, 2, 7))
async def test_real_nc_io_s2_request_completion_on_both_lanes(psq, lane, memory_type):
    env = psq
    nc = memory_type == 1
    names = ("PSQ-SPECIAL.nc" if nc else "PSQ-SPECIAL.io",)
    env.begin(names)
    address = Address(True, 0, 6, 0x120008, 0xABCD008, 3)
    data = Data(True, 0, 6, 0xFEDCBA9876543210)
    attr = Attributes(nc=nc, mmio=not nc, memory=memory_type < 4)
    await env.cycle(enqueue=SqPtr.encode(1), rob=RobPtr.encode(319, former=False), addresses=pair(address, lane), data=pair(data, lane))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()), attributes=pair(attr, lane), precommit_valid=True, precommit=SqPtr.encode(1))
    for _ in range(15):
        await env.cycle()
        if env.observed[P.p_toUncacheBuffer_req_valid]:
            break
    request = {P.p_toUncacheBuffer_req_valid: 1, P.p_toUncacheBuffer_req_bits_addr: address.paddr,
               P.p_toUncacheBuffer_req_bits_vaddr: address.vaddr, P.p_toUncacheBuffer_req_bits_data: data.data,
               P.p_toUncacheBuffer_req_bits_mask: 0xFF, P.p_toUncacheBuffer_req_bits_id: 0,
               P.p_toUncacheBuffer_req_bits_nc: int(nc), P.p_toUncacheBuffer_req_bits_memBackTypeMM: int(memory_type < 4),
               P.p_toUncacheBuffer_req_bits_robIdx_flag: 1, P.p_toUncacheBuffer_req_bits_robIdx_value: 159,
               P.p_toUncacheBuffer_req_bits_robIdx_isFormer: 0}
    env.expect(request, "S2 attributes route the original real PSQ owner to Uncache")
    await env.idle(3)
    env.expect(request, "real Uncache request remains intact under backpressure")
    await env.cycle(uncache_ready=True)
    env.expect(request, "actual Uncache request fire", before=True)
    for _ in range(3):
        await env.cycle(uncache_ack_valid=nc, uncache_ack_to_load=True)
        env.expect({**ptr_values(P.p_sqDeqPtr_, 0), P.p_writeBack_valid: 0, P.p_toRob_mmioBusy: 1}, "load-direction ack or no response cannot release this store")
    if nc:
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=False)
        env.expect({**ptr_values(P.p_sqDeqPtr_, 0), P.p_toRob_mmioBusy: 0, P.p_writeBack_valid: 0}, "NC acknowledgment moves read state but PSQ release is registered")
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        wb = {P.p_writeBack_valid: 1, P.p_writeBack_bits_debugInfo_isMMIO: 1, P.p_writeBack_bits_debugInfo_isNCIO: 0,
              P.p_writeBack_bits_robIdx_flag: 1, P.p_writeBack_bits_robIdx_value: 159,
              P.p_writeBack_bits_exceptionVec_7: 0, P.p_writeBack_bits_exceptionVec_19: 0}
        env.expect(wb, "actual IO response becomes original-owner WB")
        await env.idle(3, uncache_response=False)
        env.expect(wb, "benign IO WB retains identity during stall")
        await env.cycle(writeback_ready=True)
        env.expect(wb, "actual IO WB consumes original-owner payload", before=True)
        await env.cycle()
    env.expect({**ptr_values(P.p_sqDeqPtr_, 1), P.p_sqDeq_valid: 1, P.p_sqDeq_bits: 1}, "real PSQ handleFinish creates exactly one completed owner")
    await env.idle(3, retired=SqPtr.encode(1))
    env.expect({P.p_sqDeq_valid: 0, P.p_empty: 1, P.p_writeBack_valid: 0, P.p_writeToSbuffer_req_0_valid: 0, P.p_toUncacheBuffer_req_valid: 0}, "special owner actually completes without phantom Sbuffer writes or duplicate credits")
    env.finish(names)


@pytest.mark.parametrize("uq_lane", (0, 1))
async def test_two_real_uq_pages_split_and_single_owner_credit(psq, uq_lane):
    env = psq
    names = ("PSQ-BYTE.word", "PSQ-BYTE.line", "PSQ-BYTE.page", "PSQ-STAGE.split")
    env.begin(names)
    expected = []
    for position in range(2):
        lane = position % 2
        va, pa = 0x20FFC + position * 8192, 0xABCDFFC + position * 8192
        second = 0xD000000 + position * 0x10000
        data = 0x8877665544332211 + position * 0x1111111111111111
        first = Address(True, position, 6, va, pa, 3, unaligned=True, cross_word=True, last=False)
        page = SecondPage(True, SqPtr.encode(position), second)
        await env.cycle(enqueue=SqPtr.encode(2), addresses=pair(first, lane), data=pair(Data(True, position, 6, data), lane), second_pages=pair(page, uq_lane))
        env.expect({P.io(f"fromStoreUnit_unalignQueueReq_{uq_lane}_ready"): 1}, "real UQ accepts matching current address-prefix owner", before=True)
        await env.cycle(addresses=pair(replace(first, vaddr=va + 4, paddr=second, last=True), lane), data=(Data(), Data()),
                        attributes=pair(Attributes(last=False), lane), second_pages=(SecondPage(), SecondPage()))
        await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()))
        await env.idle(3)
        expected.extend(((va // 16 * 16, pa // 16 * 16, 0xF000, (data & 0xFFFFFFFF) << 96), (va // 16 * 16 + 16, second, 0xF, data >> 32)))
    for _ in range(12):
        await env.cycle(retired=SqPtr.encode(2))
        if env.observed[P.p_writeToSbuffer_req_1_valid]:
            break
    check_word(env, 0, *expected[0])
    check_word(env, 1, *expected[1])
    await env.cycle(sbuffer_ready=(True, False))
    check_word(env, 0, *expected[0], before=True)
    env.expect({**ptr_values(P.p_sqDeqPtr_, 0), P.p_sqDeq_valid: 0}, "first split segment cannot free its physical SQ owner")
    await consume_writes(env, expected[1:], 2, credits=2)
    env.finish(names)


@pytest.mark.parametrize("inflight", (False, True))
async def test_redirect_suffix_cancel_and_new_slot_data_complete(psq, inflight):
    env = psq
    names = ("PSQ-RECOVER.suffix", "PSQ-REUSE.cancelled", *( ("PSQ-RECOVER.inflight",) if inflight else () ))
    env.begin(names)
    old = [(Address(True, i, 6, 0x400000 + i * 4096, 0xA000000 + i * 4096, 3), Data(True, i, 6, 0x1111000000000000 + i)) for i in range(4)]
    await env.cycle(enqueue=SqPtr.encode(4), addresses=tuple(item[0] for item in old[:2]), data=tuple(item[1] for item in old[:2]))
    await env.cycle(addresses=tuple(item[0] for item in old[2:]), data=tuple(item[1] for item in old[2:]))
    if not inflight:
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
        await env.idle(3)
    await env.cycle(enqueue=SqPtr.encode(2), redirect_valid=True, redirect=SqPtr.encode(2), addresses=(Address(), Address()), data=(Data(), Data()))
    await env.cycle(redirect_valid=False, addresses=tuple(item[0] for item in old[2:]) if inflight else (Address(), Address()),
                    data=tuple(item[1] for item in old[2:]) if inflight else (Data(), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 2), **ptr_values(P.p_toLoadQueue_stDataReadySqPtr_, 2),
                **{P.io(f"toLoadQueue_st{kind}ReadyVec_{slot}"): int(slot < 2) for kind in ("Addr", "Data") for slot in range(4)}},
               "redirect keeps the original prefix and invalidates the cancelled physical suffix")
    await consume_writes(env, [scalar_word(*item) for item in old[:2]], 2, retired=SqPtr.encode(2))
    new = [(Address(True, i, 6, 0x800000 + i * 4096, 0xE000000 + i * 4096, 3), Data(True, i, 6, 0xEEEEDDCCBBAA0000 + i)) for i in range(2, 4)]
    await env.cycle(enqueue=SqPtr.encode(4), addresses=tuple(item[0] for item in new), data=tuple(item[1] for item in new), sbuffer_ready=(False, False))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await consume_writes(env, [scalar_word(*item) for item in new], 4, retired=SqPtr.encode(4))
    env.finish(names)


@pytest.mark.parametrize("base", (1, 60))
async def test_nonzero_physical_window_and_odd_tail_low_age_forward(psq, base):
    env = psq
    names = ("PSQ-FORWARD.data", "PSQ-DEQ.backpressure", "PSQ-REUSE.completed")
    env.begin(names)
    def owner(position):
        return Address(True, position % 64, 6, 0x100000 + position * 4096, 0x9000000 + position * 4096, 3), Data(True, position % 64, 6, 0xAABB000000000000 + position)
    prefix = [owner(position) for position in range(base)]
    for index in range(0, base, 2):
        group = prefix[index:index + 2]
        await env.cycle(enqueue=SqPtr.encode(base), addresses=tuple([item[0] for item in group] + [Address()] * (2 - len(group))),
                        data=tuple([item[1] for item in group] + [Data()] * (2 - len(group))))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await consume_writes(env, [scalar_word(*item) for item in prefix], base, retired=SqPtr.encode(base))
    active = [owner(position) for position in range(base, base + 64)]
    for index in range(0, 64, 2):
        await env.cycle(enqueue=SqPtr.encode(base + 64), retired=SqPtr.encode(base), addresses=tuple(item[0] for item in active[index:index + 2]),
                        data=tuple(item[1] for item in active[index:index + 2]), sbuffer_ready=(False, False))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(4)
    env.expect({**ptr_values(P.p_sqDeqPtr_, base), **ptr_values(P.p_physicalUpperSqIdx_, base + 64)}, "real physical window now straddles low and high slot domains")
    address, data = active[-1]
    query = Query(True, address.vaddr, SqPtr.encode(base + 64), 3)
    await env.cycle(queries=(query,) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    expected = {}
    for lane in range(3):
        prefix = P.io(f"forward_{lane}_s2Resp_")
        expected.update({prefix + "valid": 1, prefix + "bits_forwardInvalid": 0, prefix + "bits_matchInvalid": 0, prefix + "bits_dataInvalid_valid": 0, prefix + "bits_addrInvalid_valid": 0})
        expected.update({prefix + f"bits_forwardMask_{byte}": int(byte < 8) for byte in range(16)})
        expected.update({prefix + f"bits_forwardData_{byte}": data.data >> (8 * byte) & 255 for byte in range(8)})
    env.expect(expected, "low-domain winner keeps its new-generation byte identity on all lanes")
    await consume_writes(env, [scalar_word(*item) for item in active], base + 64, retired=SqPtr.encode(base + 64))
    env.finish(names)
