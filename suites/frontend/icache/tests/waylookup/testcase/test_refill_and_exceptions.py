"""WayLookup refill filtering and exception-pointer coverage.

Two behaviours are easy to miss with directed tests:

* a corrupt refill must be ignored (the line is not installed), and
* the exception pointer and the stage-3 redirect compare FTQ pointers, so the
  queue position (and the redirect value) matters, not just the fact that an
  exception was latched or that a redirect happened.
"""

from __future__ import annotations

import pytest

from icacheverify.waylookup.case.definitions import block
from icacheverify.waylookup.case.definitions import entry_for_block


@pytest.mark.feature("ICACHE-WAYLOOKUP-014")
async def test_corrupt_refill_leaves_the_queued_entry_unchanged(waylookup_agent):
    agent = waylookup_agent
    address = block(0x55, 0x21)
    payload = entry_for_block(address, waymask=0b0001,
                             maybe_rvc_map=0x1122_3344)
    await agent.write(payload, ftq_value=1)
    # The refill matches the queued block but is corrupt: it must not adopt
    # the new way mask or the new RVC map.
    await agent.refill(address, waymask=0b0100,
                       maybe_rvc_map=0xDEAD_BEEF, corrupt=1)
    beat = (await agent.read_beats(1))[0]
    assert beat.entry.waymask[0] == 0b0001
    assert beat.entry.maybe_rvc_map[0] == 0x1122_3344
    agent.expect_empty()
    # Drive a clean refill afterwards so the corrupt level is lowered too.
    await agent.refill(address, waymask=0, corrupt=0)


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_stage3_redirect_compares_the_ftq_pointer(waylookup_agent):
    """Only entries at or younger than the redirect target are dropped."""
    agent = waylookup_agent
    for redirect in (0, 1, 4, 5, 6, 31, 63):
        agent.expect_empty()
        await agent.write(entry_for_block(block(0x60 + redirect, 0x30),
                                          waymask=0b0001),
                          ftq_value=5, ftq_flag=0)
        await agent.stage3_flush(ftq_value=redirect, ftq_flag=0)
        if redirect <= 5:
            # Entry at FTQ 5 is at or younger than the redirect: dropped.
            await agent.expect_no_read(cycles=4)
            agent.expect_empty()
        else:
            beat = (await agent.read_beats(1))[0]
            assert beat.entry.ptag == block(0x60 + redirect, 0x30) >> 6
        await agent.flush()

    # A wrapped pointer (flag=1, value=5) is *after* an entry with flag=0
    # value=5 when the flags differ and value is not greater.
    agent.expect_empty()
    await agent.write(entry_for_block(block(0x77, 0x31), waymask=0b0001),
                      ftq_value=5, ftq_flag=0)
    await agent.stage3_flush(ftq_value=5, ftq_flag=1)
    # The wrapped redirect is after the entry, so the entry must survive.
    beat = (await agent.read_beats(1))[0]
    assert beat.entry.ptag == block(0x77, 0x31) >> 6


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_exception_latches_at_every_ring_position(waylookup_agent):
    """The exception pointer follows the write pointer across the whole ring."""
    agent = waylookup_agent
    for depth in range(31):
        await agent.flush()
        for index in range(depth):
            await agent.write(
                entry_for_block(block(0x100 + index, index & 0xFF),
                                waymask=1 << (index & 3)),
                ftq_value=index & 0x3F)
        await agent.write(
            entry_for_block(block(0x200 + depth, depth & 0xFF),
                            exception=True),
            ftq_value=depth & 0x3F)
        assert agent.rtl_write_ready() == 0, (
            f"exception at position {depth} did not stall writes")
        await agent.flush()

    # Latch an exception after the write pointer wraps: the pointer *flag* is
    # part of the stored exception pointer, and a single write is refused when
    # only one slot is free, so the pair write is the way to wrap and latch.
    agent.expect_empty()
    for index in range(30):
        await agent.write(entry_for_block(block(0x280 + index, index),
                                          waymask=1), ftq_value=index & 0x3F)
    await agent.write(entry_for_block(block(0x2A0, 0x2A), waymask=1),
                      entry_for_block(block(0x2A1, 0x2B), waymask=1),
                      ftq_value=30)
    # Write pointer is now (flag=1, value=0).  Free two slots without moving
    # the write pointer, then write the exception in the wrapped region.
    await agent.read_beats(2)
    await agent.write(
        entry_for_block(block(0x2B0, 0x2C), exception=True),
        entry_for_block(block(0x2B1, 0x2D), waymask=1),
        ftq_value=31)
    assert agent.rtl_write_ready() == 0
    await agent.flush()


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_second_output_slot_carries_the_exception_code(waylookup_agent):
    """The next entry's latched exception code appears on output slot 1."""
    import dataclasses

    from icacheverify.waylookup.transaction.types import ItlbException

    agent = waylookup_agent
    for code in (1, 2, 3, 4, 7):
        await agent.flush()
        await agent.write(entry_for_block(block(0x300, 0x40), waymask=1),
                          ftq_value=1)
        tail = entry_for_block(block(0x310, 0x41), exception=True)
        tail = dataclasses.replace(
            tail, exception=ItlbException(value=code, gpaddr=0x1234_0000,
                                          is_for_vs_non_leaf_pte=0))
        await agent.write(tail, ftq_value=2)
        await agent.read_beats(1)
        assert agent._slot1_code == code, (
            f"slot 1 exception code {agent._slot1_code} != {code}")


@pytest.mark.feature("ICACHE-WAYLOOKUP-015")
async def test_real_two_fetch_consumes_two_entries_in_one_cycle(waylookup_agent):
    """The main pipe's real-two-fetch advances the read pointer by two.

    Both output slots are valid and carry consecutive queue entries; one ready
    cycle with ``fromMainPipe_realTwoFetchValid`` pops both of them.
    """
    agent = waylookup_agent
    written = [
        entry_for_block(block(0x500 + index, 0x50 + index),
                        waymask=1 << (index & 3))
        for index in range(4)
    ]
    for index, payload in enumerate(written):
        await agent.write(payload, ftq_value=index)

    for _ in range(8):
        if agent.slot1_valid():
            break
        await agent._edge()
    first, second = await agent.read_pair()
    assert first.ptag == written[0].ptag
    # Slot 1 does not publish pTag/itlbPbmt (firtool prunes them; the main
    # pipe uses slot 0's pTag for both lines), so compare the published fields.
    assert (second.vset_idx, second.waymask, second.maybe_rvc_map,
            second.meta_codes, second.is_mmio) == (
            written[1].vset_idx, written[1].waymask, written[1].maybe_rvc_map,
            written[1].meta_codes, written[1].is_mmio)
    assert agent.occupancy() == 2, "the pair read must pop exactly two entries"
    assert agent.slot1_valid() == 1
    third, fourth = await agent.read_pair()
    assert third.ptag == written[2].ptag
    assert (fourth.vset_idx, fourth.waymask, fourth.maybe_rvc_map,
            fourth.meta_codes, fourth.is_mmio) == (
            written[3].vset_idx, written[3].waymask, written[3].maybe_rvc_map,
            written[3].meta_codes, written[3].is_mmio)
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_exception_flag_toggles_after_the_second_wrap(waylookup_agent):
    """The stored exception pointer includes the wrap bit.

    Latch one exception after the first wrap (flag=1), flush, then wrap again
    (flag=0) and latch a second one: the stored pointer flag must follow the
    write pointer in both directions.
    """
    agent = waylookup_agent

    async def fill(n: int) -> None:
        for index in range(n):
            await agent.write(entry_for_block(block(0x400 + index,
                                                    0x80 + (index & 0x3F)),
                                              waymask=1),
                              ftq_value=index & 0x3F)

    # First wrap: 30 singles + a pair = write pointer (flag=1, value=0).
    await fill(30)
    await agent.write(entry_for_block(block(0x480, 0x90), waymask=1),
                      entry_for_block(block(0x481, 0x91), waymask=1),
                      ftq_value=30)
    await agent.read_beats(2)
    await agent.write(
        entry_for_block(block(0x490, 0x92), exception=True),
        entry_for_block(block(0x491, 0x93), waymask=1),
        ftq_value=31)
    assert agent.rtl_write_ready() == 0
    await agent.flush()

    # Second wrap: 30 more singles bring the write pointer back to flag=0.
    await fill(30)
    await agent.write(entry_for_block(block(0x4A0, 0x94), exception=True),
                      ftq_value=1)
    assert agent.rtl_write_ready() == 0
    await agent.flush()


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_stage3_flush_releases_the_latched_exception(waylookup_agent):
    """Dropping the exception entry with a stage-3 redirect frees the queue.

    The exception entry is the youngest; dropping it must clear the latch so
    that the write port (stalled while an exception is pending) reopens.
    """
    agent = waylookup_agent
    await agent.write(entry_for_block(block(0x4B0, 0x95), waymask=1),
                      ftq_value=6)
    await agent.write(entry_for_block(block(0x4B1, 0x96), exception=True),
                      ftq_value=7)
    assert agent.rtl_write_ready() == 0
    await agent.stage3_flush(ftq_value=7)
    assert agent.rtl_write_ready() == 1, (
        "a stage-3 flush of the exception entry must release the write stall")
    await agent.write(entry_for_block(block(0x4C0, 0x97), waymask=1),
                      ftq_value=8)


@pytest.mark.feature("ICACHE-WAYLOOKUP-001")
async def test_ftq_pointer_flags_are_stored(waylookup_agent):
    """The queue stores the FTQ pointer's wrap bit, not only its value."""
    agent = waylookup_agent
    for flag in (1, 0):
        await agent.write(entry_for_block(block(0x4D0 + flag, 0x98),
                                          waymask=1),
                          ftq_value=5, ftq_flag=flag)
        await agent.write(entry_for_block(block(0x4D2 + flag, 0x99),
                                          waymask=1),
                          entry_for_block(block(0x4D3 + flag, 0x9A),
                                          waymask=1),
                          ftq_flag=flag)
        await agent.read_beats(3)
    agent.expect_empty()
