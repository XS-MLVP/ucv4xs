"""Real128 virtual uops, all8 sources and full SQ/ROB identities across wraps."""
from dataclasses import replace

from lsqverify.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load


async def test_all_eight_dispatch_sources_fill_128_real_store_uops_and_finish_full_generations(lsq):
    trace = MemoryOwners(lsq)
    position, program = 0, 10
    for lane in range(8):
        start = position
        wave = [StoreOwner(start + offset, RobPtr.encode(program + offset, former=not bool(offset & 1)),
                           0x200000 + (start + offset) * 16, 0xA200000 + (start + offset) * 16,
                           value=0x1234567800000000 + start + offset) for offset in range(128)]
        # One uop each call: real sparse source lane,128 distinct virtual
        # owners simultaneously retained, NOT one16-flow snapshot per group.
        for owner in wave:
            await trace.dispatch(stores=[owner], store_lane=lane)
        load = cached_load(lane, RobPtr.encode(program + 128, former=not bool(lane & 1)), start + 128,
                           0x400000 + lane * 64, 0xB400000 + lane * 64)
        await trace.dispatch(loads=[load])
        await trace.execute([load])
        await trace.idle(3)
        assert trace.sq_head == start and not lsq.observed["io_sqEmpty"]
        assert sum(not state["completed"] for state in trace.stores.values()) == 128
        await trace.write_all(range(start, start + 64))
        # Only the actual executed first64 can retire. No ROB movement over
        # the younger unwritten physical window, despite full virtual depth.
        mid = RobPtr.encode(program + 64)
        trace.base = replace(trace.base, pending=mid, pending_next=mid, sbuffer_ready=(True, True))
        for _ in range(160):
            await trace.cycle()
            if trace.sq_head == start + 64:
                break
        assert trace.sq_head == start + 64
        trace.base = replace(trace.base, sbuffer_ready=(False, False))
        await trace.write_all(range(start + 64, start + 128))
        await trace.finish(pending=RobPtr.encode(program + 129))
        assert trace.sq_head == start + 128 and all(state["completed"] for state in trace.stores.values())
        position += 128
        program += 129
    assert position == len(trace.stores) == 1024 and trace.load_released == 8
    lsq.prove("LSQ-ALLOC.all_lanes", "LSQ-ALLOC.sq_capacity", "LSQ-ALLOC.sq_wrap", "LSQ-RETIRE.ordinary")
