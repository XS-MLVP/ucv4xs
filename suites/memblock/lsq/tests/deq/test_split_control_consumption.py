"""Observe the real output transfer, not only a newly queued valid."""

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.deq.types import Store
from suites.memblock.lsq.raw.types import SqPtr


@pytest.mark.parametrize("neighbor_committed", (False, True))
@pytest.mark.parametrize("stall", (0, 3))
async def test_actual_split_tail_fire_keeps_ordinary_store_wline(deq, neighbor_committed, stall):
    env = deq
    first = Store(vaddr=0x9400C, page=0xABCD, byte_mask=0xFF, data=0x8877665544332211,
                  address_valid=True, data_valid=True, committed=True, cross_word=True)
    neighbor = Store(vaddr=0xA0000, page=0xDEAD, byte_mask=0xFFFF, data=0, address_valid=True,
                     data_valid=True, committed=neighbor_committed, cache_operation=True, cbo=3)
    env.begin(("DEQ-SPLIT.zero_neighbor",))
    await env.cycle(stores=(first, neighbor), sbuffer_ready=(False, False), valid_count=2)
    env.expect({P.p_rdataPtrMoveCnt: 1}, "one split owner accepted, not the adjacent zero", before=True)
    # Read advances to the neighbor, but it has no head permission until the
    # older split really completes. No extra data is admitted during draining.
    neighbor = Store(vaddr=neighbor.vaddr, page=neighbor.page, byte_mask=neighbor.byte_mask, data=0,
                     address_valid=True, data_valid=True, committed=False, cache_operation=True, cbo=3)
    for _ in range(stall):
        await env.cycle(stores=(neighbor, Store()), read_ptr=SqPtr.encode(1))
    await env.cycle(stores=(neighbor, Store()), read_ptr=SqPtr.encode(1), sbuffer_ready=(True, True))
    env.expect({P.p_writeToSbuffer_req_0_valid: 1, P.p_writeToSbuffer_req_1_valid: 1}, "both original split segments actually fire", before=True)
    env.expect({P.p_writeToSbuffer_req_1_bits_addr: first.page * 4096 + 16,
                P.p_writeToSbuffer_req_1_bits_vaddr: 0x94010, P.p_writeToSbuffer_req_1_bits_mask: 0xF,
                P.p_writeToSbuffer_req_1_bits_data: 0x88776655, P.p_writeToSbuffer_req_1_bits_wline: 0},
               "actual tail transfer belongs to ordinary split, never to the adjacent whole-line zero", before=True,
               bit_masks={P.p_writeToSbuffer_req_1_bits_data: 0xFFFFFFFF})
    env.finish(("DEQ-SPLIT.zero_neighbor",))
