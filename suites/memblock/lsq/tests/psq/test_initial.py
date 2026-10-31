
from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


def ptr_values(prefix, position):
    ptr = SqPtr.encode(position)
    return {prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value}


def read_ptr(pins, prefix=P.p_sqDeqPtr_):
    return pins[prefix + "first_flag"] * 128 + pins[prefix + "second_flag"] * 64 + pins[prefix + "value"]


def lane_pair(value, lane):
    return tuple(value if index == lane else type(value)() for index in range(2))


def check_word(env, lane, va, pa, mask, data, *, wline=0, before=False):
    prefix = P.io(f"writeToSbuffer_req_{lane}_")
    env.expect({prefix + "valid": 1, prefix + "bits_vaddr": va, prefix + "bits_addr": pa, prefix + "bits_mask": mask,
                prefix + "bits_data": data, prefix + "bits_wline": wline}, "real PSQ source bytes and control at Sbuffer",
               before=before, bit_masks={prefix + "bits_data": sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)})


async def drain_to(env, target, *, expected_sbuffer, expected_credits=1):
    consumed = credits = 0
    quiet = 0
    for _ in range(30):
        await env.cycle(sbuffer_ready=(True, True))
        consumed += sum(env.pre_observed[P.io(f"writeToSbuffer_req_{lane}_valid")] for lane in range(2))
        if env.pre_observed[P.p_sqDeq_valid]:
            credits += env.pre_observed[P.p_sqDeq_bits]
        quiet = quiet + 1 if read_ptr(env.observed) == target else 0
        if quiet == 4:
            break
    assert quiet == 4 and consumed == expected_sbuffer and credits == expected_credits
    env.expect({**ptr_values(P.p_sqDeqPtr_, target), P.p_writeToSbuffer_req_0_valid: 0, P.p_writeToSbuffer_req_1_valid: 0,
                P.p_toUncacheBuffer_req_valid: 0, P.p_writeBack_valid: 0}, "actual parent completion, not queue acceptance")


async def test_reset_has_no_old_requests_ready_or_dequeue(psq):
    env = psq
    names = ("PSQ-RESET.initial",)
    env.begin(names)
    await env.idle(3)
    env.expect({P.p_empty: 1, P.p_full: 0, P.p_sqDeq_valid: 0, P.p_writeBack_valid: 0, P.p_toUncacheBuffer_req_valid: 0,
                P.p_toDCache_req_valid: 0, P.p_writeToSbuffer_req_0_valid: 0, P.p_writeToSbuffer_req_1_valid: 0,
                **ptr_values(P.p_sqDeqPtr_, 0), **ptr_values(P.p_physicalUpperSqIdx_, 64),
                **ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 0), **ptr_values(P.p_toLoadQueue_stDataReadySqPtr_, 0)}, "reset convergence on all real parent control interfaces")
    env.expect({P.io(f"toLoadQueue_st{kind}ReadyVec_{slot}"): 0 for kind in ("Addr", "Data") for slot in range(64)}, "no initialized readiness from unreset payload")
    env.finish(names)


@pytest.mark.parametrize("lane", (0, 1))
@pytest.mark.parametrize("order", ("addr_first", "data_first", "together"))
@pytest.mark.parametrize("permission", ("retired", "precommit"))
async def test_real_write_order_forward_and_sbuffer_completion(psq, lane, order, permission):
    env = psq
    names = ("PSQ-WRITE." + order, "PSQ-WRITE.lanes", "PSQ-READY.address", "PSQ-READY.data", "PSQ-PERMIT.none",
             "PSQ-PERMIT." + permission, "PSQ-FORWARD.data", "PSQ-DEQ.credit", "PSQ-DEQ.backpressure", "PSQ-STAGE.s2")
    env.begin(names)
    address = Address(True, 0, 6, 0x10008, 0xABC008, 3)
    data = Data(True, 0, 6, 0x8877665544332211)
    await env.cycle(enqueue=SqPtr.encode(1), addresses=lane_pair(address, lane) if order != "data_first" else (Address(), Address()),
                    data=lane_pair(data, lane) if order != "addr_first" else (Data(), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    if order != "together":
        ready = "Addr" if order == "addr_first" else "Data"
        not_ready = "Data" if ready == "Addr" else "Addr"
        env.expect({**ptr_values(P.io(f"toLoadQueue_st{ready}ReadySqPtr_"), 1), **ptr_values(P.io(f"toLoadQueue_st{not_ready}ReadySqPtr_"), 0)}, "independent address/data prefix before the other half arrives")
        await env.cycle(addresses=lane_pair(address, lane) if order == "data_first" else (Address(), Address()),
                        data=lane_pair(data, lane) if order == "addr_first" else (Data(), Data()))
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
        await env.idle(3)
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 1), **ptr_values(P.p_toLoadQueue_stDataReadySqPtr_, 1),
                P.p_toLoadQueue_stAddrReadyVec_0: 1, P.p_toLoadQueue_stDataReadyVec_0: 1,
                P.p_writeToSbuffer_req_0_valid: 0, P.p_sqDeq_valid: 0, **ptr_values(P.p_sqDeqPtr_, 0)}, "ready does not grant ROB permission or release the SQ")
    query = Query(True, address.vaddr, SqPtr.encode(1), 3)
    await env.cycle(queries=(query,) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    expected = {}
    for load_lane in range(3):
        prefix = P.io(f"forward_{load_lane}_s2Resp_")
        expected.update({prefix + "valid": 1, prefix + "bits_forwardInvalid": 0, prefix + "bits_matchInvalid": 0,
                         prefix + "bits_addrInvalid_valid": 0, prefix + "bits_dataInvalid_valid": 0})
        for byte in range(16):
            expected[prefix + f"bits_forwardMask_{byte}"] = int(byte >= 8)
            if byte >= 8:
                expected[prefix + f"bits_forwardData_{byte}"] = data.data >> (8 * (byte - 8)) & 255
    env.expect(expected, "three actual ForwardModule lanes read the real PSQ-written bytes")
    permit = {"retired": SqPtr.encode(1)} if permission == "retired" else {"precommit_valid": True, "precommit": SqPtr.encode(1)}
    for _ in range(10):
        await env.cycle(**permit)
        if env.observed[P.p_writeToSbuffer_req_0_valid]:
            break
    check_word(env, 0, 0x10000, 0xABC000, 0xFF00, data.data << 64)
    for _ in range(3):
        await env.cycle()
        check_word(env, 0, 0x10000, 0xABC000, 0xFF00, data.data << 64)
        env.expect(ptr_values(P.p_sqDeqPtr_, 0), "Sbuffer backpressure cannot release PSQ ownership")
    await drain_to(env, 1, expected_sbuffer=1)
    await env.cycle(retired=SqPtr.encode(1))
    await env.idle(3)
    env.expect({P.p_empty: 1}, "retirement and real writeout eventually converge")
    env.finish(names)


@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
@pytest.mark.parametrize("hold", (0, 2))
async def test_real_parent_cache_error_at_actual_wb_fire(psq, denied, corrupt, hold):
    env = psq
    names = ("PSQ-SPECIAL.wb_error" if hold else "PSQ-SPECIAL.wb_response",)
    env.begin(names)
    await env.cycle(enqueue=SqPtr.encode(1), rob=RobPtr.encode(319, former=False),
                    addresses=(Address(True, 0, 1, (1 << 49) + 0x12340, 0xA12340, 3, hyper=True), Address()),
                    data=(Data(True, 0, 1, 0x1122334455667788), Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()), precommit_valid=True, precommit=SqPtr.encode(1))
    for _ in range(15):
        await env.cycle()
        if env.observed[P.p_toDCache_req_valid]:
            break
    env.expect({P.p_toDCache_req_valid: 1, P.p_toDCache_req_bits_address: 0xA12340, P.p_toDCache_req_bits_opcode: 0}, "real PSQ CBO path issues original address/opcode")
    await env.cycle(cache_ready=True)
    env.expect({P.p_toDCache_resp_ready: 1}, "real parent accepted cache request")
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    wb = {P.p_writeBack_valid: 1, P.p_writeBack_bits_exceptionVec_7: int(denied), P.p_writeBack_bits_exceptionVec_19: int(corrupt),
          P.p_writeBack_bits_robIdx_flag: 1, P.p_writeBack_bits_robIdx_value: 159, P.p_writeBack_bits_robIdx_isFormer: 0,
          P.p_exceptionInfo_bits_vaddr: (1 << 49) + 0x12340, P.p_exceptionInfo_bits_isHyper: 1}
    env.expect(wb, "real PSQ reports the accepted cache response errors and stored identity")
    for _ in range(hold):
        await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False)
        env.expect({P.p_writeBack_valid: 1}, "parent writeback remains pending while consumer stalls")
    await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False, writeback_ready=True)
    env.expect(wb, "actual real-parent WB transfer must retain the accepted error", before=True)
    await drain_to(env, 1, expected_sbuffer=0)
    env.finish(names)


@pytest.mark.parametrize("stall", (0, 3))
async def test_real_parent_split_tail_actual_fire_is_not_neighbor_zero(psq, stall):
    env = psq
    names = ("PSQ-SPECIAL.split_wline",)
    env.begin(names)
    first = Address(True, 0, 6, 0x9400C, 0xABCD00C, 3, unaligned=True, cross_word=True, last=False)
    zero = Address(True, 1, 7, 0xA0000, 0xDEAD000, 3)
    await env.cycle(enqueue=SqPtr.encode(2), addresses=(first, zero), data=(Data(True, 0, 6, 0x8877665544332211), Data(True, 1, 7, (1 << 128) - 1)))
    await env.cycle(addresses=(replace(first, vaddr=0x94010, paddr=0xABCD010, last=True), Address()),
                    attributes=(Attributes(last=False), Attributes()), data=(Data(), Data()))
    await env.cycle(addresses=(Address(), Address()), attributes=(Attributes(), Attributes()), precommit_valid=True, precommit=SqPtr.encode(1))
    for _ in range(15):
        await env.cycle()
        if env.observed[P.p_writeToSbuffer_req_1_valid]:
            break
    env.expect({P.p_writeToSbuffer_req_0_valid: 1, P.p_writeToSbuffer_req_1_valid: 1}, "real PSQ split produced two queued segments")
    await env.idle(stall)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x94000, 0xABCD000, 0xF000, 0x44332211 << 96, before=True)
    check_word(env, 1, 0x94010, 0xABCD010, 0xF, 0x88776655, before=True)
    env.finish(names)
