
import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.deq.types import DeqControl, Store
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


def store(vaddr, data, *, memory_type=0):
    return Store(vaddr=vaddr, page=0xABC, byte_mask=0xFF, data=data, memory_type=memory_type,
                 data_valid=True, address_valid=True, committed=True)


@pytest.mark.parametrize("memory_type", (1, 5, 2, 7))
@pytest.mark.parametrize("offset", (0, 8))
async def test_real_nc_and_io_request_completion_paths(deq, memory_type, offset):
    env = deq
    source = store(0x10000 + offset, 0x8877665544332211, memory_type=memory_type)
    nc = memory_type in (1, 5)
    names = (("DEQ-NC.memory" if memory_type == 1 else "DEQ-NC.device", "DEQ-NC.direction", "DEQ-NC.hold", "DEQ-CREDIT.nc") if nc else
             ("DEQ-MMIO.memory" if memory_type == 2 else "DEQ-MMIO.device", "DEQ-CREDIT.mmio"))
    env.begin(names)
    await env.cycle(stores=(source, Store()), rob=RobPtr.encode(7), valid_count=1)
    request = {P.p_toUncacheBuffer_req_valid: 1, P.p_toUncacheBuffer_req_bits_addr: source.paddr,
               P.p_toUncacheBuffer_req_bits_vaddr: source.vaddr, P.p_toUncacheBuffer_req_bits_data: source.data,
               P.p_toUncacheBuffer_req_bits_mask: 0xFF, P.p_toUncacheBuffer_req_bits_id: 0,
               P.p_toUncacheBuffer_req_bits_nc: int(nc), P.p_toUncacheBuffer_req_bits_memBackTypeMM: int(memory_type < 4),
               P.p_toUncacheBuffer_req_bits_robIdx_value: 7, P.p_toUncacheBuffer_req_bits_robIdx_isFormer: 1}
    env.expect(request, "original NC/IO request carries correct 64-bit half, PA/VA and ROB")
    await env.idle(2)
    env.expect(request, "Uncache request remains stable under backpressure")
    await env.cycle(uncache_ready=True)
    env.expect({P.p_toUncacheBuffer_req_valid: 0, P.p_toRob_mmioBusy: 1, P.p_writeBack_valid: 0}, "accepted request waits for its own completion")
    if nc:
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=True)
        env.expect({P.p_toRob_mmioBusy: 1, P.p_writeBack_valid: 0, P.p_rdataPtrMoveCnt: 0}, "load idResp cannot advance NC store")
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=False)
        env.expect({P.p_rdataPtrMoveCnt: 1}, "store idResp advances the NC read pointer", before=True)
        env.expect({P.p_toRob_mmioBusy: 0, P.p_writeBack_valid: 0, P.p_sqDeqCnt: 0}, "NC request acknowledgement is not final SQ completion")
        await env.cycle(stores=(Store(), Store()), uncache_ack_valid=False)
        await env.cycle(uncache_response=True)
        env.expect({P.p_writeBack_valid: 0, P.p_sqDeqCnt: 0}, "later NC response is handled by PSQ rather than MMIO writeback state")
        await env.cycle(uncache_response=False, dequeue_controls=(DeqControl(committed=True, finished=True), DeqControl()))
    else:
        await env.idle(2)
        env.expect({P.p_writeBack_valid: 0, P.p_rdataPtrMoveCnt: 0}, "MMIO cannot finish without real response")
        await env.cycle(uncache_response=True)
        wb = {P.p_writeBack_valid: 1, P.p_writeBack_bits_robIdx_value: 7, P.p_writeBack_bits_exceptionVec_7: 0,
              P.p_writeBack_bits_exceptionVec_19: 0, P.p_writeBack_bits_debugInfo_isMMIO: 1, P.p_writeBack_bits_debugInfo_isNCIO: 0}
        env.expect(wb, "MMIO response becomes original-identity writeback")
        await env.idle(2, uncache_response=False)
        env.expect(wb, "benign MMIO writeback waits for ready")
        await env.cycle(writeback_ready=True)
        env.expect({P.p_writeBack_valid: 1, P.p_rdataPtrMoveCnt: 1}, "MMIO read pointer moves only on actual writeback fire", before=True)
        await env.cycle(stores=(Store(), Store()), dequeue_controls=(DeqControl(committed=True, finished=True), DeqControl()))
    env.expect({P.p_sqDeqCnt: 1}, "real PSQ finish feedback supplies one completion credit", before=True)
    await env.cycle(dequeue_controls=(DeqControl(), DeqControl()), valid_count=0)
    env.expect({P.p_sqDeqCnt: 0, P.p_writeBack_valid: 0, P.p_toUncacheBuffer_req_valid: 0}, "one owner completes without duplicate credit or request")
    env.finish(names)


async def test_real_child_odd_tail_storage_survives_single_then_double_acceptance(deq):
    env = deq
    first, second, third = store(0x10000, 0x1111111111111111), store(0x20000, 0x2222222222222222), store(0x30000, 0x3333333333333333)
    names = ("DEQ-CACHE.two", "DEQ-BACKPRESSURE.compact", "DEQ-CREDIT.real_fire")
    env.begin(names)
    await env.cycle(stores=(first, Store()), sbuffer_ready=(False, False), valid_count=1)
    await env.cycle(stores=(Store(), Store()), sbuffer_ready=(True, False))
    env.expect({P.p_writeToSbuffer_req_0_valid: 1, P.p_writeToSbuffer_req_0_bits_data: first.data}, "first real store consumed before odd-tail reuse", before=True)
    await env.cycle(stores=(second, third), sbuffer_ready=(False, False), read_ptr=SqPtr.encode(1), valid_count=3)
    env.expect({P.p_rdataPtrMoveCnt: 2}, "two new records accepted at the odd internal tail", before=True)
    await env.cycle(stores=(Store(), Store()))
    env.expect({P.p_writeToSbuffer_req_0_valid: 1, P.p_writeToSbuffer_req_0_bits_data: second.data,
                P.p_writeToSbuffer_req_1_valid: 1, P.p_writeToSbuffer_req_1_bits_data: third.data}, "both physical storage positions preserve distinct actual payload")
    await env.cycle(sbuffer_ready=(True, True))
    env.expect({P.p_sqDeqCnt: 2, P.p_writeToSbuffer_req_0_valid: 0, P.p_writeToSbuffer_req_1_valid: 0}, "two real Sbuffer fires supply two credits")
    await env.cycle()
    env.expect({P.p_sqDeqCnt: 0}, "odd-tail credits are not duplicated")
    env.finish(names)
