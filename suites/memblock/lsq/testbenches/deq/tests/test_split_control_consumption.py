"""Observe the real output transfer, not only a newly queued valid."""

import pytest

from suites.memblock.lsq.testbenches.deq.transactions import Observation as DeqObservation
from suites.memblock.lsq.testbenches.deq.transactions import SbufferWord
from suites.memblock.lsq.testbenches.deq.transactions import Store
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr


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
    env.expect(DeqObservation(read_pointer_moves=1), "one split owner accepted, not the adjacent zero", before=True)
    # Read advances to the neighbor, but it has no head permission until the
    # older split really completes. No extra data is admitted during draining.
    neighbor = Store(vaddr=neighbor.vaddr, page=neighbor.page, byte_mask=neighbor.byte_mask, data=0,
                     address_valid=True, data_valid=True, committed=False, cache_operation=True, cbo=3)
    for _ in range(stall):
        await env.cycle(stores=(neighbor, Store()), read_ptr=SqPtr.encode(1))
    await env.cycle(stores=(neighbor, Store()), read_ptr=SqPtr.encode(1), sbuffer_ready=(True, True))
    env.expect(DeqObservation(sbuffer_word_0=SbufferWord(), sbuffer_word_1=SbufferWord()),
               "both original split segments actually fire", before=True)
    env.expect_sbuffer_word(
        1, SbufferWord(valid=None, addr=first.page * 4096 + 16, vaddr=0x94010, mask=0xF, data=0x88776655, wline=0),
        "actual tail transfer belongs to ordinary split, never to the adjacent whole-line zero",
        data_mask=0xFFFFFFFF, before=True)
    env.finish(("DEQ-SPLIT.zero_neighbor",))
