"""Flush paths of ICacheWayLookup.

Two distinct mechanisms share the module:

``flush``           - unconditional reset of both pointers (fetch redirect/fence.i)
``flushFromBpu.s3`` - drop exactly the youngest entry when the redirect target is
                      not younger than the FTQ block that entry was written for

The stage-3 path is the interesting one: it must drop only the youngest entry,
and only when the FTQ index matches, otherwise the queue must survive intact.
"""

from __future__ import annotations

import pytest
from toffee import ClockCycles

from icacheverify.waylookup.case.definitions import entry
from icacheverify.waylookup.driver.encoding import encode_control
from icacheverify.waylookup.driver.encoding import encode_write
from icacheverify.waylookup.transaction.types import WayLookupWrite


@pytest.mark.feature("ICACHE-WAYLOOKUP-004")
async def test_flush_allows_reuse_of_the_whole_queue(waylookup_agent):
    agent = waylookup_agent
    for index in range(6):
        await agent.write(entry(0x3000 + index), ftq_value=index)

    await agent.flush()
    agent.expect_empty()

    # The full depth must be writable again after a flush.
    depth = agent.model.depth
    for index in range(depth - 1):
        if not agent.model.write_ready():
            raise AssertionError(f"queue only accepted {index} writes after flush")
        await agent.write(entry(0x3100 + index), ftq_value=index % 64)
    assert agent.occupancy() == depth - 1


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_stage3_flush_drops_only_the_youngest_entry(waylookup_agent):
    agent = waylookup_agent
    first, second, third = entry(0x4001), entry(0x4002), entry(0x4003)

    # All three entries belong to FTQ block 7; the youngest is `third`.
    for payload in (first, second, third):
        await agent.write(payload, ftq_value=7)
    assert agent.tags() == (first.ptag, second.ptag, third.ptag)

    await agent.stage3_flush(ftq_value=7)

    assert agent.occupancy() == 2, "stage-3 flush must drop exactly one entry"
    assert agent.tags() == (first.ptag, second.ptag)

    beats = await agent.read_beats(2)
    assert [beat.entry.ptag for beat in beats] == [first.ptag, second.ptag]


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_redirect_older_than_the_tail_drops_the_youngest(waylookup_agent):
    """``shouldFlushByStage3`` drops when the redirect is *not after* the tail.

    RTL: ``valid && s3.valid && !isAfter(s3.bits, tailFtqIdx)``. Redirecting to
    block 3 while the youngest entry belongs to block 9 means the tail is on the
    wrong path, so the youngest entry must be dropped - not kept.
    """
    agent = waylookup_agent
    older, younger = entry(0x5001), entry(0x5002)

    await agent.write(older, ftq_value=3)
    await agent.write(younger, ftq_value=9)
    assert agent.tags() == (older.ptag, younger.ptag)

    await agent.stage3_flush(ftq_value=3)

    assert agent.occupancy() == 1, "a redirect older than the tail drops the youngest entry"
    assert agent.tags() == (older.ptag,)
    beats = await agent.read_beats(1)
    assert [beat.entry.ptag for beat in beats] == [older.ptag]


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_redirect_younger_than_the_tail_keeps_the_queue(waylookup_agent):
    """A redirect *after* the tail block leaves every entry on the path."""
    agent = waylookup_agent
    older, younger = entry(0x6001), entry(0x6002)

    await agent.write(older, ftq_value=3)
    await agent.write(younger, ftq_value=3)
    assert agent.tags() == (older.ptag, younger.ptag)

    # Redirect to block 9 is younger than the tail block 3, so nothing is dropped.
    await agent.stage3_flush(ftq_value=9)

    assert agent.occupancy() == 2
    beats = await agent.read_beats(2)
    assert [beat.entry.ptag for beat in beats] == [older.ptag, younger.ptag]


@pytest.mark.feature("ICACHE-WAYLOOKUP-005")
async def test_stage3_flush_on_empty_queue_is_harmless(waylookup_agent):
    agent = waylookup_agent
    agent.expect_empty()

    await agent.stage3_flush(ftq_value=5)

    assert agent.occupancy() == 0
    agent.expect_empty()
    await agent.expect_no_read(cycles=4)


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_exception_entry_stalls_writes_until_flush(waylookup_agent):
    """A latched I-TLB exception blocks new prefetch writes.

    RTL: ``write.ready := free >= FetchPorts && !exceptionEntry.valid``. The
    stall is released by ``flush``, which also clears the latched entry.
    """
    agent = waylookup_agent
    payload = entry(0x7001, exception=True)

    agent.expect_empty()
    assert agent.model.write_ready() == 1
    await agent.write(payload, ftq_value=4)

    # The exception is now latched: no further write may be accepted.
    assert agent.model.write_ready() == 0, "latched exception must stall writes"
    assert agent.rtl_write_ready() == 0, "RTL must stop advertising write.ready"

    await agent.flush()
    agent.expect_empty()
    assert agent.model.write_ready() == 1
    assert agent.rtl_write_ready() == 1, "flush must release the exception stall"


@pytest.mark.feature("ICACHE-WAYLOOKUP-006")
async def test_exception_entry_is_read_out_with_its_payload(waylookup_agent):
    """The latched exception is visible on both read slots and blocks writes."""
    agent = waylookup_agent
    head = entry(0x7001)
    exception = entry(0x7101, exception=True)
    await agent.write(head, ftq_value=4)
    await agent.write(exception, ftq_value=5)
    assert agent.rtl_write_ready() == 0, "the latched exception must stall writes"

    first = await agent.read_beats(1)
    assert first[0].entry.ptag == head.ptag
    # The exception is now the next entry, so the second output slot must carry
    # its exception payload while the head is read.
    second = await agent.read_beats(1)
    assert second[0].entry.ptag == exception.ptag
    assert second[0].entry.exception.value == exception.exception.value
    assert second[0].entry.exception.gpaddr == exception.exception.gpaddr
    assert second[0].entry.exception.is_for_vs_non_leaf_pte == (
        exception.exception.is_for_vs_non_leaf_pte)
    await agent.flush()
    assert agent.rtl_write_ready() == 1


@pytest.mark.feature("ICACHE-WAYLOOKUP-020")
@pytest.mark.xfail(strict=True, reason=(
    "ICacheWayLookup latches exceptionEntry from a write that the same-cycle "
    "flush cancels, so the empty queue never re-advertises write.ready and the "
    "prefetch pipe stalls until another full flush.  Unreachable from the "
    "ICache because the prefetch pipe gates its write with s1_flush, but the "
    "module's own contract requires the flush to clear the memo."))
async def test_flush_in_the_write_cycle_discards_the_entry_and_its_exception(waylookup_agent):
    """A write cancelled by a redirect must leave no exception state behind.

    The prefetch pipe can present an entry carrying an ITLB exception on the
    same edge that a redirect flushes the queue.  The entry is discarded, so its
    exception memo must be discarded with it: otherwise the queue reports zero
    occupancy but refuses every subsequent write, and the producer stalls until
    another full flush clears the memo.  The stale pointer itself does not leak
    into a later entry - the slot it names is rewritten before it can be read -
    so the observable damage is the stall, not a wrong exception.
    """
    agent = waylookup_agent
    payload = entry(0x7201, exception=True)
    agent.write_payload_drivers[0].set(
        encode_write(WayLookupWrite(entry=payload, ftq_flag=0, ftq_value=4)))
    agent.write_valid_drivers[0].set({"valid": 1})
    agent.control_driver.set(encode_control(flush=1))
    await ClockCycles(agent.dut.clock, 1)
    agent.write_valid_drivers[0].set({"valid": 0})
    agent.control_driver.set(encode_control())
    agent.model.step(flush=1, write_fire=1,
                     write_entries=(agent._resident(payload),))
    await ClockCycles(agent.dut.clock, 1)
    agent.model.step()

    agent.expect_empty()
    assert agent.rtl_write_ready() == 1, (
        "the flushed write latched its exception and stalled the empty queue")

    follower = entry(0x7301)
    await agent.write(follower, ftq_value=5)
    beat = (await agent.read_beats(1))[0]
    assert beat.entry.ptag == follower.ptag
    assert beat.entry.exception.value == 0, (
        "a stale exception from the flushed write was attached to a new entry")
