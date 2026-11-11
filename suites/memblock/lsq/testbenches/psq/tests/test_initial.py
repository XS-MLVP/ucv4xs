from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.tests.helpers import cache
from suites.memblock.lsq.testbenches.psq.tests.helpers import exception
from suites.memblock.lsq.testbenches.psq.tests.helpers import forward
from suites.memblock.lsq.testbenches.psq.tests.helpers import observation
from suites.memblock.lsq.testbenches.psq.tests.helpers import rob
from suites.memblock.lsq.testbenches.psq.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.psq.tests.helpers import word
from suites.memblock.lsq.testbenches.psq.tests.helpers import writeback
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


def lane_pair(value, lane):
    return tuple(value if index == lane else type(value)() for index in range(2))


def check_word(env, lane, va, pa, mask, data, *, wline=0, before=False):
    byte_mask = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
    env.expect_sbuffer_word(lane, word(addr=pa, vaddr=va, mask=mask, data=data, wline=wline),
                            "real PSQ source bytes and control at Sbuffer", data_mask=byte_mask, before=before)


async def drain_to(env, target, *, expected_sbuffer, expected_credits=1):
    consumed = credits = 0
    quiet = 0
    for _ in range(30):
        await env.cycle(sbuffer_ready=(True, True))
        consumed += int(env.pre_response.sbuffer_word_0 is not None)
        consumed += int(env.pre_response.sbuffer_word_1 is not None)
        if env.pre_response.dequeue_valid:
            credits += env.pre_response.dequeue_count
        quiet = quiet + 1 if env.deq_position == target else 0
        if quiet == 4:
            break
    assert quiet == 4 and consumed == expected_sbuffer and credits == expected_credits
    env.expect(observation(sq_deq_ptr=sqptr(target), sbuffer_word_0=None, sbuffer_word_1=None,
                           uncache_request=None, writeback=None),
               "actual parent completion, not queue acceptance")


async def test_reset_has_no_old_requests_ready_or_dequeue(psq):
    env = psq
    names = ("PSQ-RESET.initial",)
    env.begin(names)
    await env.idle(3)
    env.expect(observation(empty=1, full=0, dequeue_valid=0, writeback=None, uncache_request=None, cache_request=None,
                           sbuffer_word_0=None, sbuffer_word_1=None, sq_deq_ptr=sqptr(0), physical_upper=sqptr(64),
                           addr_ready_ptr=sqptr(0), data_ready_ptr=sqptr(0)), "reset convergence")
    env.expect(observation(addr_ready_clear_mask=(1 << 64) - 1, data_ready_clear_mask=(1 << 64) - 1),
               "no initialized readiness from unreset payload")
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
        first, second = ("addr_ready_ptr", "data_ready_ptr") if order == "addr_first" else ("data_ready_ptr", "addr_ready_ptr")
        env.expect(observation(**{first: sqptr(1), second: sqptr(0)}), "independent address/data prefix before the other half arrives")
        await env.cycle(addresses=lane_pair(address, lane) if order == "data_first" else (Address(), Address()),
                        data=lane_pair(data, lane) if order == "addr_first" else (Data(), Data()))
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
        await env.idle(3)
    env.expect(observation(addr_ready_ptr=sqptr(1), data_ready_ptr=sqptr(1), addr_ready_mask=1, data_ready_mask=1,
                           sbuffer_word_0=None, dequeue_valid=0, sq_deq_ptr=sqptr(0)),
               "ready does not grant ROB permission or release the SQ")
    query = Query(True, address.vaddr, SqPtr.encode(1), 3)
    await env.cycle(queries=(query,) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    expected = [forward(valid=1, forward_invalid=0, match_invalid=0, addr_invalid=0, data_invalid=0,
                        forward_mask=0xFF00, forward_data=data.data << 64) for _ in range(3)]
    env.expect(observation(forward=tuple(expected)), "three actual ForwardModule lanes read the real PSQ-written bytes")
    permit = {"retired": SqPtr.encode(1)} if permission == "retired" else {"precommit_valid": True, "precommit": SqPtr.encode(1)}
    for _ in range(10):
        await env.cycle(**permit)
        if env.response.sbuffer_word_0 is not None:
            break
    check_word(env, 0, 0x10000, 0xABC000, 0xFF00, data.data << 64)
    for _ in range(3):
        await env.cycle()
        check_word(env, 0, 0x10000, 0xABC000, 0xFF00, data.data << 64)
        env.expect(observation(sq_deq_ptr=sqptr(0)), "Sbuffer backpressure cannot release PSQ ownership")
    await drain_to(env, 1, expected_sbuffer=1)
    await env.cycle(retired=SqPtr.encode(1))
    await env.idle(3)
    env.expect(observation(empty=1), "retirement and real writeout eventually converge")
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
        if env.response.cache_request is not None:
            break
    env.expect(observation(cache_request=cache(address=0xA12340, opcode=0)), "real PSQ CBO path issues original address/opcode")
    await env.cycle(cache_ready=True)
    env.expect(observation(cache_response_ready=1), "real parent accepted cache request")
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    wb = observation(writeback=writeback(rob_identity=rob(159, 1, 0), access_fault=int(denied), bus_error=int(corrupt)),
                     exception_info=exception(vaddr=(1 << 49) + 0x12340, hyper=1, valid=None))
    env.expect(wb, "real PSQ reports the accepted cache response errors and stored identity")
    for _ in range(hold):
        await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False)
        env.expect(observation(writeback=writeback()), "parent writeback remains pending while consumer stalls")
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
        if env.response.sbuffer_word_1 is not None:
            break
    env.expect(observation(sbuffer_word_0=word(), sbuffer_word_1=word()), "real PSQ split produced two queued segments")
    await env.idle(stall)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x94000, 0xABCD000, 0xF000, 0x44332211 << 96, before=True)
    check_word(env, 1, 0x94010, 0xABCD010, 0xF, 0x88776655, before=True)
    env.finish(names)
