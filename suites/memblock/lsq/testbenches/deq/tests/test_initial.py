import pytest

from dataclasses import replace

from suites.memblock.lsq.testbenches.deq.transactions import CacheRequest
from suites.memblock.lsq.testbenches.deq.transactions import ExceptionInfo
from suites.memblock.lsq.testbenches.deq.transactions import Observation as DeqObservation
from suites.memblock.lsq.testbenches.deq.transactions import RobIdentity
from suites.memblock.lsq.testbenches.deq.transactions import SbufferWord
from suites.memblock.lsq.testbenches.deq.transactions import Writeback
from suites.memblock.lsq.testbenches.deq.transactions import Store
from suites.memblock.lsq.testbenches.deq.transactions import SecondPage
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


def source(vaddr=0x10000, size=4, data=0x8877665544332211, **kwargs):
    return Store(vaddr=vaddr, page=0xABC, byte_mask=(1 << size) - 1, data=data,
                 data_valid=True, address_valid=True, committed=True, cross_word=vaddr % 16 + size > 16, **kwargs)


def sbuffer_word(store, word, *, paddr=None):
    """Direct byte-address mapping, no rotation function shared with RTL."""
    word_va = store.vaddr // 16 * 16 + 16 * word
    word_pa = store.paddr // 16 * 16 + 16 * word if paddr is None else paddr
    mask, data = 0, 0
    for index in range(16):
        if store.byte_mask >> index & 1:
            address = store.vaddr + index
            if word_va <= address < word_va + 16:
                byte = address - word_va
                mask |= 1 << byte
                data |= (store.data >> (index * 8) & 255) << (8 * byte)
    return {"vaddr": word_va, "addr": word_pa, "mask": mask, "data": data, "wline": 0}


def check_word(env, lane, expected, *, before=False):
    # Unmasked byte payload is not a correctness obligation.
    mask = sum(255 << (byte * 8) for byte in range(16) if expected["mask"] >> byte & 1)
    env.expect_sbuffer_word(lane, SbufferWord(**expected), "actual Sbuffer word address/mask and byte-origin data",
                            data_mask=mask, before=before)


async def test_reset_idle_and_force_write_hysteresis(deq):
    env = deq
    names = ("DEQ-RESET.initial", "DEQ-IDLE.disabled", "DEQ-DRAIN.force_write")
    env.begin(names)
    expected = DeqObservation(uncache_request=None, cache_request=None, writeback=None,
                              sbuffer_word_0=None, sbuffer_word_1=None, read_pointer_moves=0, sq_deq_count=0)
    for count, force in ((0, 0), (59, 0), (60, 1), (64, 1), (59, 1), (55, 1), (54, 0), (55, 0)):
        await env.cycle(valid_count=count)
        env.expect(replace(expected, force_write=force), "physical occupancy force-write registered hysteresis")
    env.finish(names)


@pytest.mark.parametrize("offset", (0, 3, 7, 12))
async def test_single_cacheable_store_credit_waits_for_actual_sbuffer_consumption(deq, offset):
    env = deq
    store = source(vaddr=0x10000 + offset, size=4)
    names = ("DEQ-CACHE.single", "DEQ-BYTE.offset", "DEQ-BYTE.source", "DEQ-BACKPRESSURE.hold", "DEQ-CREDIT.real_fire")
    env.begin(names)
    await env.cycle(stores=(store, Store()), sbuffer_ready=(False, False), valid_count=1)
    env.expect(DeqObservation(read_pointer_moves=1, sq_deq_count=0, sbuffer_word_0=None),
               "store enters real queue without SQ credit", before=True)
    await env.cycle(stores=(Store(), Store()))
    check_word(env, 0, sbuffer_word(store, 0))
    for _ in range(3):
        await env.cycle()
        check_word(env, 0, sbuffer_word(store, 0))
        env.expect(DeqObservation(sq_deq_count=0), "backpressured queued store has no completion credit")
    await env.cycle(sbuffer_ready=(True, False))
    check_word(env, 0, sbuffer_word(store, 0), before=True)
    env.expect(DeqObservation(sbuffer_word_0=None, sq_deq_count=1, deq_pointer_next=1), "credit after actual Sbuffer fire")
    await env.cycle()
    env.expect(DeqObservation(sq_deq_count=0), "completion credit is not duplicated")
    env.finish(names)


async def test_two_stores_compact_without_mixing_data_or_credit(deq):
    env = deq
    first, second = source(data=0x11111111), source(vaddr=0x20004, data=0x22222222)
    names = ("DEQ-CACHE.two", "DEQ-BACKPRESSURE.compact", "DEQ-CREDIT.real_fire")
    env.begin(names)
    await env.cycle(stores=(first, second), sbuffer_ready=(False, False), valid_count=2)
    env.expect(DeqObservation(read_pointer_moves=2, sq_deq_count=0), "two distinct stores accepted without early SQ release", before=True)
    await env.cycle(stores=(Store(), Store()))
    check_word(env, 0, sbuffer_word(first, 0))
    check_word(env, 1, sbuffer_word(second, 0))
    await env.cycle(sbuffer_ready=(True, False))
    check_word(env, 0, sbuffer_word(second, 0))
    env.expect(DeqObservation(sq_deq_count=1), "first consumed store receives one credit")
    await env.cycle()
    check_word(env, 0, sbuffer_word(second, 0), before=True)
    env.expect(DeqObservation(sq_deq_count=1, sbuffer_word_0=None), "compacted second store completes independently")
    await env.cycle()
    env.expect(DeqObservation(sq_deq_count=0), "both credits complete exactly once")
    env.finish(names)


@pytest.mark.parametrize("cross_page", (False, True))
async def test_split_store_has_two_physical_segments_but_only_one_credit(deq, cross_page):
    env = deq
    store = source(vaddr=0x10FFC if cross_page else 0x1000C, size=8)
    page = SecondPage(True, 0xDEF000, SqPtr()) if cross_page else SecondPage()
    names = ("DEQ-SPLIT.page" if cross_page else "DEQ-SPLIT.word", "DEQ-BYTE.source", "DEQ-CREDIT.split")
    env.begin(names)
    await env.cycle(stores=(store, Store()), second_page=page, sbuffer_ready=(False, False), valid_count=1)
    env.expect(DeqObservation(read_pointer_moves=1, sq_deq_count=0), "one split store, not two SQ entries", before=True)
    if cross_page:
        env.expect(DeqObservation(unalign_ready=1), "matching UQ second page consumed with split acceptance", before=True)
    await env.cycle(stores=(Store(), Store()), second_page=SecondPage())
    check_word(env, 0, sbuffer_word(store, 0))
    check_word(env, 1, sbuffer_word(store, 1, paddr=page.paddr if cross_page else None))
    await env.cycle(sbuffer_ready=(True, False))
    env.expect(DeqObservation(sq_deq_count=0), "first split segment must not release the SQ store")
    check_word(env, 0, sbuffer_word(store, 1, paddr=page.paddr if cross_page else None))
    await env.cycle()
    env.expect(DeqObservation(sq_deq_count=1, sbuffer_word_0=None), "second actual segment produces exactly one credit")
    await env.cycle()
    env.expect(DeqObservation(sq_deq_count=0), "split credit cannot repeat")
    env.finish(names)


@pytest.mark.parametrize("denied,corrupt", ((False, False), (True, False), (False, True), (True, True)))
@pytest.mark.parametrize("hold", (0, 3))
async def test_cache_cbo_response_errors_survive_writeback_backpressure(deq, denied, corrupt, hold):
    env = deq
    store = source(vaddr=0x12340, cache_operation=True, cbo=0, hyper=True)
    names = ("DEQ-CBO.drain", "DEQ-CBO.request_hold", "DEQ-EXCEPTION.response", "DEQ-EXCEPTION.identity", *( ("DEQ-EXCEPTION.held",) if hold and (denied or corrupt) else () ))
    env.begin(names)
    await env.cycle(stores=(store, Store()), rob=RobPtr.encode(159, former=False), valid_count=1, sbuffer_empty=False)
    env.expect(DeqObservation(flush=1, cache_request=None), "CBO must wait for Sbuffer drain")
    await env.idle(2)
    env.expect(DeqObservation(flush=1, cache_request=None), "flush is not completed by elapsed cycles")
    await env.cycle(sbuffer_empty=True)
    request = DeqObservation(cache_request=CacheRequest(address=store.paddr, opcode=0))
    env.expect(request, "actual cache CBO request")
    await env.idle(2)
    env.expect(request, "cache request is stable under backpressure")
    await env.cycle(cache_ready=True)
    env.expect(DeqObservation(cache_response_ready=1), "CBO request accepted and waiting for real response")
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt, writeback_ready=False)
    response = DeqObservation(
        writeback=Writeback(rob=RobIdentity(159, None, 0), access_fault=int(denied), bus_error=int(corrupt)),
        exception_info=ExceptionInfo(vaddr=store.vaddr, hyper=1, access_fault=int(denied), bus_error=int(corrupt)))
    env.expect(response, "response faults and original identity must be reported")
    for _ in range(hold):
        await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False)
        env.expect(response, "writeback errors must remain stable until actual ready/fire")
    await env.cycle(cache_response=False, writeback_ready=True)
    env.expect(response, "writeback consumes original errors and identity", before=True)
    await env.cycle(stores=(Store(), Store()))
    env.expect(DeqObservation(writeback=None), "CBO writeback completes once")
    env.finish(names)
