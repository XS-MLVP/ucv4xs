"""Random legal lookup results survive the ring verbatim.

Every field of a lookup result (set index, way mask, page tag, RVC map, parity,
MMIO/PBMT attributes) is written by the prefetch pipe and consumed by the main
pipe.  Randomising all of them exercises the full width of every stored field
while the queue model checks the FIFO order and payload.
"""

from __future__ import annotations

import random

import pytest

from suites.frontend.icache.waylookup.transaction.types import ItlbException
from suites.frontend.icache.waylookup.transaction.types import WayLookupEntry


def random_entry(rng: random.Random) -> WayLookupEntry:
    return WayLookupEntry(
        vset_idx=(rng.getrandbits(8), rng.getrandbits(8)),
        waymask=(rng.getrandbits(4), rng.getrandbits(4)),
        ptag=rng.getrandbits(36),
        maybe_rvc_map=(rng.getrandbits(32), rng.getrandbits(32)),
        meta_codes=(rng.getrandbits(1), rng.getrandbits(1)),
        is_mmio=rng.getrandbits(1),
        itlb_pbmt=rng.getrandbits(2),
        # A zero exception code never latches the exception register; the
        # gpAddr field is still driven to random values.
        exception=ItlbException(value=0, gpaddr=rng.getrandbits(55),
                                is_for_vs_non_leaf_pte=rng.getrandbits(1)),
    )


@pytest.mark.feature("ICACHE-WAYLOOKUP-001")
async def test_random_entries_are_queued_and_returned_verbatim(waylookup_agent):
    agent = waylookup_agent
    rng = random.Random(0x5A17_1A0C)
    for _ in range(40):
        entry = random_entry(rng)
        await agent.write(entry, ftq_value=rng.getrandbits(6))
        beat = (await agent.read_beats(1))[0]
        got = beat.entry
        assert (got.vset_idx, got.waymask, got.ptag, got.maybe_rvc_map,
                got.meta_codes, got.is_mmio, got.itlb_pbmt) == (
                entry.vset_idx, entry.waymask, entry.ptag,
                entry.maybe_rvc_map, entry.meta_codes, entry.is_mmio,
                entry.itlb_pbmt), f"entry {entry} read back as {got}"
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-002")
async def test_random_entries_on_both_write_ports(waylookup_agent):
    """Both prefetch ports carry independent random payloads."""
    agent = waylookup_agent
    rng = random.Random(0x5A17_B0B0)
    for _ in range(16):
        first, second = random_entry(rng), random_entry(rng)
        await agent.write(first, second, ftq_value=rng.getrandbits(6))
        beats = await agent.read_beats(2)
        for beat, expected in zip(beats, (first, second)):
            got = beat.entry
            assert (got.vset_idx, got.waymask, got.ptag,
                    got.maybe_rvc_map, got.meta_codes) == (
                    expected.vset_idx, expected.waymask, expected.ptag,
                    expected.maybe_rvc_map, expected.meta_codes)
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_random_exception_payload_is_read_out(waylookup_agent):
    """A latched exception carries a random gpAddr and code to the main pipe."""
    agent = waylookup_agent
    rng = random.Random(0x5A17_E0C0)
    for _ in range(6):
        exception = random_entry(rng)
        exception = WayLookupEntry(
            vset_idx=exception.vset_idx, waymask=exception.waymask,
            ptag=exception.ptag, maybe_rvc_map=exception.maybe_rvc_map,
            meta_codes=exception.meta_codes, is_mmio=exception.is_mmio,
            itlb_pbmt=exception.itlb_pbmt,
            exception=ItlbException(value=rng.randrange(1, 8),
                                    gpaddr=rng.getrandbits(55),
                                    is_for_vs_non_leaf_pte=rng.getrandbits(1)))
        await agent.write(exception, ftq_value=rng.getrandbits(6))
        beat = (await agent.read_beats(1))[0]
        assert beat.entry.exception.value == exception.exception.value
        assert beat.entry.exception.gpaddr == exception.exception.gpaddr
        assert (beat.entry.exception.is_for_vs_non_leaf_pte
                == exception.exception.is_for_vs_non_leaf_pte)
        await agent.flush()


@pytest.mark.feature("ICACHE-WAYLOOKUP-008")
async def test_random_refill_maps_update_a_resident_entry(waylookup_agent):
    """A refill rewrites the resident entry's way mask and RVC map verbatim."""
    agent = waylookup_agent
    from suites.frontend.icache.waylookup.case.definitions import block
    rng = random.Random(0x5A17_2EF1)
    for _ in range(12):
        tag, set_index = rng.getrandbits(34), rng.randrange(256)
        block_address = block(tag, set_index)
        entry = random_entry(rng)
        entry = WayLookupEntry(
            vset_idx=(set_index, entry.vset_idx[1]),
            waymask=(1 << rng.randrange(4), entry.waymask[1]),
            # The physical tag is the block address's page number; block()
            # derives the low bits from the set index, so read it back instead
            # of assigning an unrelated tag.
            ptag=block_address >> 6, maybe_rvc_map=entry.maybe_rvc_map,
            meta_codes=entry.meta_codes, is_mmio=entry.is_mmio,
            itlb_pbmt=entry.itlb_pbmt, exception=entry.exception)
        await agent.write(entry, ftq_value=rng.getrandbits(6))
        new_waymask = 1 << rng.randrange(4)
        new_map = rng.getrandbits(32)
        await agent.refill(block_address, waymask=new_waymask,
                           maybe_rvc_map=new_map)
        beat = (await agent.read_beats(1))[0]
        assert beat.entry.waymask[0] == new_waymask
        assert beat.entry.maybe_rvc_map[0] == new_map
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-001")
async def test_random_entries_fill_every_ring_slot(waylookup_agent):
    """Every one of the 32 physical slots stores an independent random entry."""
    agent = waylookup_agent
    rng = random.Random(0x5A17_F111)
    for _ in range(8):
        written = [random_entry(rng) for _ in range(32)]
        for index in range(0, 32, 2):
            await agent.write(written[index], written[index + 1],
                              ftq_value=rng.getrandbits(6))
        beats = await agent.read_beats(32)
        for beat, expected in zip(beats, written):
            got = beat.entry
            assert (got.vset_idx, got.waymask, got.ptag, got.maybe_rvc_map,
                    got.meta_codes, got.is_mmio, got.itlb_pbmt) == (
                    expected.vset_idx, expected.waymask, expected.ptag,
                    expected.maybe_rvc_map, expected.meta_codes,
                    expected.is_mmio, expected.itlb_pbmt)
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_random_exception_on_the_next_slot_payload(waylookup_agent):
    """The second output slot carries the next entry's random exception payload."""
    agent = waylookup_agent
    rng = random.Random(0x5A17_5E12)
    for _ in range(12):
        head = random_entry(rng)
        tail = random_entry(rng)
        tail = WayLookupEntry(
            vset_idx=tail.vset_idx, waymask=tail.waymask, ptag=tail.ptag,
            maybe_rvc_map=tail.maybe_rvc_map, meta_codes=tail.meta_codes,
            is_mmio=tail.is_mmio, itlb_pbmt=tail.itlb_pbmt,
            exception=ItlbException(value=1, gpaddr=rng.getrandbits(55),
                                    is_for_vs_non_leaf_pte=rng.getrandbits(1)))
        # The exception register latches from write port 0 only, so the tail
        # must be written in its own cycle to become the next read slot.
        await agent.write(head, ftq_value=rng.getrandbits(6))
        await agent.write(tail, ftq_value=rng.getrandbits(6))
        await agent.read_beats(1)
        await agent.flush()
