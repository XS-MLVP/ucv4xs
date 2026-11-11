"""128 real vector flows; ready span is NOT virtual occupancy or AND-ready."""

from dataclasses import asdict, replace

from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import SbufferWord, SqPointerExpectation
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


def owner(position):
    address = Address(True, position % 64, 6, 0x8000 + 16 * position,
                      0xA0808000 + 16 * position, 3, rob=RobPtr.encode(1 + position // 16), mask=255)
    data = Data(True, SqPtr.encode(position), 6, 0x1020304050607000 + position)
    return address, data


async def test_real_128_vector_flows_ready_spans_six_stage_perf_and_two_windows(lsq):
    base = Inputs()
    consumed = released = 0
    written = set()

    async def cycle(packet=None):
        nonlocal consumed, released
        packet = packet or base
        await lsq.cycle(packet)
        pre, post = lsq.pre_response, lsq.response
        for lane in range(2):
            word = (pre.sbuffer_word_0, pre.sbuffer_word_1)[lane]
            if word is not None and packet.sbuffer_ready[lane]:
                assert consumed in written
                address, data = owner(consumed)
                lsq.expect_sbuffer_word(lane, SbufferWord(addr=address.paddr, vaddr=address.vaddr,
                    data=data.data, mask=255, wline=0), "original vector flow actually consumed once in program order",
                    before=True, data_mask=(1 << 64) - 1)
                lsq.emit("vector_sbuffer_fire", uid=consumed + 1, sq=asdict(data.sq), lane=lane)
                consumed += 1
        if post.sq_dequeue.valid:
            released += post.sq_dequeue.count
            assert released <= consumed <= 128
        assert pre.uncache_request is None and pre.mmio_stout is None
        assert not post.lq_dequeue.valid

    dispatch = tuple(Dispatch(True, 2, RobPtr.encode(1 + lane), 16, store_end=SqPtr.encode(16 * (lane + 1))) for lane in range(8))
    lsq.emit("allocate_vector_bus_span", domain="NORMAL-PRODUCER", dispatch=[asdict(d) for d in dispatch],
             owners=[dict(uid=pos + 1, address=asdict(owner(pos)[0]), data=asdict(owner(pos)[1])) for pos in range(128)])
    await cycle(replace(base, dispatch=dispatch))
    for _ in range(10):
        await cycle()
    lsq.expect(obs(sq_full=0, force_write=1, sq_deq_ptr=SqPointerExpectation(value=0)), "legal 128 virtual flows, only first 64 physical owners may issue")
    issued = 0
    for target in (15, 16, 17, 32, 33, 48, 49, 64):
        while issued < target:
            addresses = tuple(owner(pos)[0] for pos in range(issued, min(issued + 2, target)))
            await cycle(replace(base, addresses=addresses + (Address(),) * (2 - len(addresses))))
            issued += len(addresses)
        for _ in range(10):
            await cycle()
        bits = [int(target < 16), int(16 < target <= 32), int(32 < target <= 48), int(target > 48)]
        lsq.expect(obs(perf=(None,) * 31 + tuple(bits) + (0, 0, 0, 1)),
                   "address-only ready span quartile differs from unready data and 128 virtual flows")
        assert consumed == released == 0
        lsq.emit("vector_ready_span_boundary", physical=target, data_ready=0, virtual=128)
    for first in range(0, 64, 2):
        values = tuple(owner(pos)[1] for pos in (first, first + 1))
        await cycle(replace(base, data=values))
        written.update((first, first + 1))
    for _ in range(6):
        await cycle()
    # Only the first four uops' 64 flows have executed. One shared ROB may
    # retire those, not the four still-unissued younger vector instructions.
    base = replace(base, pending=RobPtr.encode(5), pending_next=RobPtr.encode(5), sbuffer_ready=(True, True))
    for _ in range(100):
        await cycle()
        if released == consumed == 64:
            break
    assert released == consumed == 64 and not lsq.response.sq_empty
    base = replace(base, sbuffer_ready=(False, False))
    # Reuse the same 64 physical slots with their next full SQ generation.
    for first in range(64, 128, 2):
        await cycle(replace(base, addresses=tuple(owner(pos)[0] for pos in (first, first + 1))))
    for first in range(64, 128, 2):
        await cycle(replace(base, data=tuple(owner(pos)[1] for pos in (first, first + 1))))
        written.update((first, first + 1))
    for _ in range(6):
        await cycle()
    base = replace(base, pending=RobPtr.encode(9), pending_next=RobPtr.encode(9), sbuffer_ready=(True, True))
    for _ in range(140):
        await cycle()
        if released == consumed == 128 and lsq.response.sq_empty:
            break
    assert released == consumed == 128 and lsq.response.sq_empty and lsq.response.lq_empty
    for _ in range(10):
        await cycle()
    lsq.expect(obs(force_write=0, uncache_request=None, replay_allocate=0), "all original vector effects and credits truly drained")
    lsq.prove("LSQ-ALLOC.multi_flow", "LSQ-ALLOC.all_lanes", "LSQ-ALLOC.sq_capacity", "LSQ-RETIRE.multi_flow")
