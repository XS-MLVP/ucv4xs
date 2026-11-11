
import pytest

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.env.directed import scalar_word
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.env.directed import consume
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import forward
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import observation
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import word
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch


@pytest.mark.parametrize("lane", (0, 7))
@pytest.mark.parametrize("flows", (1, 3))
@pytest.mark.parametrize("permit", ("precommit", "retired"))
async def test_real_vsq_to_psq_writeout_and_physical_release_feedback(sq, lane, flows, permit):
    env = sq
    names = ("SQ-PERMIT.none", "SQ-PERMIT." + permit, "SQ-READY.independent", "SQ-WRITE.lanes", "SQ-FORWARD.data", "SQ-DISPATCH.sparse")
    if flows > 1:
        names += ("SQ-DISPATCH.multi", "SQ-CREDIT.last_flow")
    if permit == "retired":
        names += ("SQ-RETIRE.buffered",)
    env.begin(names)
    dispatch = tuple(Dispatch(True, True, RobPtr.encode(10), flows, SqPtr.encode(flows)) if i == lane else Dispatch() for i in range(8))
    await env.cycle(dispatch=dispatch)
    await env.cycle(dispatch=(Dispatch(),) * 8)
    owners = [(Address(True, index, 6, 0x100008 + index * 4096, 0xA000008 + index * 4096, 3),
               Data(True, index, 6, 0x8877665544332200 + index)) for index in range(flows)]
    write_lane = int(lane == 7)
    for address, data in owners:
        await env.cycle(addresses=tuple(address if i == write_lane else Address() for i in range(2)))
        await env.cycle(addresses=(Address(), Address()), data=tuple(data if i != write_lane else Data() for i in range(2)))
        await env.cycle(data=(Data(), Data()))
    await env.idle(5)
    env.expect(observation(sbuffer_word_0=None, dequeue_valid=0, empty=0,
                           addr_ready_ptr=sqptr(flows), data_ready_ptr=sqptr(flows)),
               "real VSQ has no ROB-head/retired permission yet, despite complete physical bytes")
    address, data = owners[-1]
    await env.cycle(queries=(Query(True, address.vaddr, SqPtr.encode(flows), 3),) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    forwarded = sum((data.data >> (8 * byte) & 0xFF) << (8 * (byte + 8)) for byte in range(8))
    env.expect(observation(forward=tuple(forward(valid=1, forward_invalid=0, match_invalid=0,
                                                 addr_invalid=0, data_invalid=0,
                                                 forward_mask=0xFF00, forward_data=forwarded)
                                             for _ in range(3))),
               "original STA/STD bytes reach all three actual integrated forward lanes")
    await env.idle(12, rob_head=RobPtr.encode(10 if permit == "precommit" else 11))
    env.expect(observation(sbuffer_word_0=word(), empty=0, sq_deq_ptr=sqptr(0)),
               "real VSQ permission reaches real PSQ, but buffered writes are not yet completed")
    await consume(env, [scalar_word(*owner) for owner in owners], flows)
    env.finish(names)


async def test_combined_initial_empty_reset_has_no_phantom_credit(sq):
    env = sq
    names = ("SQ-RESET.initial",)
    env.begin(names)
    env.expect(observation(empty=1, full=0, dequeue_valid=0, redirect_valid=0, recover_stall=0,
                           sq_deq_ptr=sqptr(0), physical_upper=sqptr(64)),
               "both real queues converge empty without fabricated dynamic WFI/inactive ports")
    env.finish(names)
