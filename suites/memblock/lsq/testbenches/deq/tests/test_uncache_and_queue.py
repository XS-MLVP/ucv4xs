import pytest

from suites.memblock.lsq.testbenches.deq.transactions import Observation as DeqObservation
from suites.memblock.lsq.testbenches.deq.transactions import RobIdentity
from suites.memblock.lsq.testbenches.deq.transactions import SbufferWord
from suites.memblock.lsq.testbenches.deq.transactions import UncacheRequest
from suites.memblock.lsq.testbenches.deq.transactions import Writeback
from suites.memblock.lsq.testbenches.deq.transactions import DeqControl
from suites.memblock.lsq.testbenches.deq.transactions import Store
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


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
    request = DeqObservation(uncache_request=UncacheRequest(
        addr=source.paddr, vaddr=source.vaddr, data=source.data, mask=0xFF, ident=0,
        nc=int(nc), memory_backed=int(memory_type < 4), rob=RobIdentity(7, None, 1)))
    env.expect(request, "original NC/IO request carries correct 64-bit half, PA/VA and ROB")
    await env.idle(2)
    env.expect(request, "Uncache request remains stable under backpressure")
    await env.cycle(uncache_ready=True)
    env.expect(DeqObservation(uncache_request=None, mmio_busy=1, writeback=None),
               "accepted request waits for its own completion")
    if nc:
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=True)
        env.expect(DeqObservation(mmio_busy=1, writeback=None, read_pointer_moves=0),
                   "load idResp cannot advance NC store")
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=False)
        env.expect(DeqObservation(read_pointer_moves=1), "store idResp advances the NC read pointer", before=True)
        env.expect(DeqObservation(mmio_busy=0, writeback=None, sq_deq_count=0),
                   "NC request acknowledgement is not final SQ completion")
        await env.cycle(stores=(Store(), Store()), uncache_ack_valid=False)
        await env.cycle(uncache_response=True)
        env.expect(DeqObservation(writeback=None, sq_deq_count=0),
                   "later NC response is handled by PSQ rather than MMIO writeback state")
        await env.cycle(uncache_response=False, dequeue_controls=(DeqControl(committed=True, finished=True), DeqControl()))
    else:
        await env.idle(2)
        env.expect(DeqObservation(writeback=None, read_pointer_moves=0), "MMIO cannot finish without real response")
        await env.cycle(uncache_response=True)
        wb = DeqObservation(writeback=Writeback(rob=RobIdentity(7), access_fault=0, bus_error=0, mmio=1, ncio=0))
        env.expect(wb, "MMIO response becomes original-identity writeback")
        await env.idle(2, uncache_response=False)
        env.expect(wb, "benign MMIO writeback waits for ready")
        await env.cycle(writeback_ready=True)
        env.expect(DeqObservation(writeback=Writeback(rob=RobIdentity(7)), read_pointer_moves=1),
                   "MMIO read pointer moves only on actual writeback fire", before=True)
        await env.cycle(stores=(Store(), Store()), dequeue_controls=(DeqControl(committed=True, finished=True), DeqControl()))
    env.expect(DeqObservation(sq_deq_count=1), "real PSQ finish feedback supplies one completion credit", before=True)
    await env.cycle(dequeue_controls=(DeqControl(), DeqControl()), valid_count=0)
    env.expect(DeqObservation(sq_deq_count=0, writeback=None, uncache_request=None),
               "one owner completes without duplicate credit or request")
    env.finish(names)


async def test_real_child_odd_tail_storage_survives_single_then_double_acceptance(deq):
    env = deq
    first, second, third = store(0x10000, 0x1111111111111111), store(0x20000, 0x2222222222222222), store(0x30000, 0x3333333333333333)
    names = ("DEQ-CACHE.two", "DEQ-BACKPRESSURE.compact", "DEQ-CREDIT.real_fire")
    env.begin(names)
    await env.cycle(stores=(first, Store()), sbuffer_ready=(False, False), valid_count=1)
    await env.cycle(stores=(Store(), Store()), sbuffer_ready=(True, False))
    env.expect(DeqObservation(sbuffer_word_0=SbufferWord(data=first.data)),
               "first real store consumed before odd-tail reuse", before=True)
    await env.cycle(stores=(second, third), sbuffer_ready=(False, False), read_ptr=SqPtr.encode(1), valid_count=3)
    env.expect(DeqObservation(read_pointer_moves=2), "two new records accepted at the odd internal tail", before=True)
    await env.cycle(stores=(Store(), Store()))
    env.expect(DeqObservation(sbuffer_word_0=SbufferWord(data=second.data),
                              sbuffer_word_1=SbufferWord(data=third.data)),
               "both physical storage positions preserve distinct actual payload")
    await env.cycle(sbuffer_ready=(True, True))
    env.expect(DeqObservation(sq_deq_count=2, sbuffer_word_0=None, sbuffer_word_1=None),
               "two real Sbuffer fires supply two credits")
    await env.cycle()
    env.expect(DeqObservation(sq_deq_count=0), "odd-tail credits are not duplicated")
    env.finish(names)
