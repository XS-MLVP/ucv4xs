"""Way-lookup ring storage: every slot and both write ports, plus the BPU tail flush.

The queue is a 32-entry ring written by the prefetch pipe (one entry per fetch,
two for a dual fetch) and read by the main pipe.  A queue that is only correct
at one pointer value would silently return another fetch's way; these cases
sweep the pointer through every slot with both write-port combinations and check
that each fetched block still returns its own instructions.
"""

from __future__ import annotations

import pytest

from icacheverify.icache.case.definitions import make_fetch


@pytest.mark.feature("ICACHE-ICACHE-022")
async def test_ring_stores_every_slot_through_both_write_ports(icache_agent):
    agent = icache_agent
    # Resident blocks used to advance the write pointer cheaply.
    single = make_fetch(0x50000, 15)
    pair0 = make_fetch(0x51000, 15)   # set 0x40, banks 0..3
    pair1 = make_fetch(0x51060, 15)   # set 0x41, banks 4..7: Interleave
    await agent.send(single)
    await agent.send(pair0, pair1)
    pointer = 3  # one single write + one dual write

    for target in range(32):
        # Place the dual write so its second entry lands in slot `target`:
        # writePtr must be target-1.  Single writes move the pointer by one.
        while pointer != (target - 1) % 32:
            await agent.send(single)
            pointer = (pointer + 1) % 32
        await agent.send(pair0, pair1)
        pointer = (pointer + 2) % 32

    # The ring must still return both blocks of the last dual fetch and the
    # single block (functional check through the model on every send above).
    observed = await agent.send(pair0, pair1)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1

    # A cold miss written into the last slot is corrected by its refill while
    # no other write is in flight: the queue's in-place update must reach the
    # final slot as well, not only the slot at the read pointer.
    while pointer != 31:
        await agent.send(single)
        pointer = (pointer + 1) % 32
    cold = make_fetch(0x81000, 15)
    observed = await agent.send(cold)
    assert observed.ifu_valid == 1


@pytest.mark.feature("ICACHE-ICACHE-023")
async def test_bpu_stage3_flush_drops_the_queue_tail(icache_agent):
    agent = icache_agent
    req = make_fetch(0x52000, 15, ftq_idx=5)
    await agent.prefetch_only(req)
    assert agent._bit(agent.ports.ftq_main_ready) == 1, "the entry must be queued"

    # A redirect younger than the tail must leave the queue alone.
    await agent.bpu_s3_flush(flag=0, value=6)
    assert agent._bit(agent.ports.ftq_main_ready) == 1

    # A redirect for the tail pointer drops the speculative entry.
    await agent.bpu_s3_flush(flag=0, value=5)
    assert agent._bit(agent.ports.ftq_main_ready) == 0, (
        "the BPU stage-3 flush must release the last queue entry")
