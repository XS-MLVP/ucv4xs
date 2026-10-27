"""128 real vector flows; ready span is NOT virtual occupancy or AND-ready."""
from dataclasses import asdict, replace

from lsqverify.lsq_wrapper.types import Address, Data, Dispatch, Inputs
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr


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
        pre, post = lsq.pre_observed, lsq.observed
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p + "valid"] and packet.sbuffer_ready[lane]:
                assert consumed in written
                address, data = owner(consumed)
                lsq.expect({p + "bits_addr": address.paddr, p + "bits_vaddr": address.vaddr,
                            p + "bits_data": data.data, p + "bits_mask": 255, p + "bits_wline": 0},
                           "original vector flow actually consumed once in program order", before=True,
                           masks={p + "bits_data": (1 << 64) - 1})
                lsq.emit("vector_sbuffer_fire", uid=consumed + 1, sq=asdict(data.sq), lane=lane)
                consumed += 1
        if post["io_toLsqEnqCtrl_sqDeq_valid"]:
            released += post["io_toLsqEnqCtrl_sqDeq_bits"]
            assert released <= consumed <= 128
        assert not pre["io_uncache_req_valid"] and not pre["io_mmioStout_valid"]
        assert not post["io_toLsqEnqCtrl_lqDeq_valid"]

    dispatch = tuple(Dispatch(True, 2, RobPtr.encode(1 + lane), 16, store_end=SqPtr.encode(16 * (lane + 1))) for lane in range(8))
    lsq.emit("allocate_vector_bus_span", domain="NORMAL-PRODUCER", dispatch=[asdict(d) for d in dispatch],
             owners=[dict(uid=pos + 1, address=asdict(owner(pos)[0]), data=asdict(owner(pos)[1])) for pos in range(128)])
    await cycle(replace(base, dispatch=dispatch))
    for _ in range(10):
        await cycle()
    lsq.expect({"io_sqFull": 0, "io_force_write": 1, "io_sqDeqPtr_value": 0}, "legal 128 virtual flows, only first 64 physical owners may issue")
    issued = 0
    for target in (15, 16, 17, 32, 33, 48, 49, 64):
        while issued < target:
            addresses = tuple(owner(pos)[0] for pos in range(issued, min(issued + 2, target)))
            await cycle(replace(base, addresses=addresses + (Address(),) * (2 - len(addresses))))
            issued += len(addresses)
        for _ in range(10):
            await cycle()
        bits = [int(target < 16), int(16 < target <= 32), int(32 < target <= 48), int(target > 48)]
        lsq.expect({**{f"io_perf_{31 + lane}_value": value for lane, value in enumerate(bits)},
                    "io_perf_35_value": 0, "io_perf_36_value": 0, "io_perf_37_value": 0, "io_perf_38_value": 1},
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
    assert released == consumed == 64 and not lsq.observed["io_sqEmpty"]
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
        if released == consumed == 128 and lsq.observed["io_sqEmpty"]:
            break
    assert released == consumed == 128 and lsq.observed["io_sqEmpty"] and lsq.observed["io_lqEmpty"]
    for _ in range(10):
        await cycle()
    lsq.expect({"io_force_write": 0, "io_uncache_req_valid": 0, "io_replayAllocate": 0}, "all original vector effects and credits truly drained")
    lsq.prove("LSQ-ALLOC.multi_flow", "LSQ-ALLOC.all_lanes", "LSQ-ALLOC.sq_capacity", "LSQ-RETIRE.multi_flow")
