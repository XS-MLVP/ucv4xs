"""FIFO residency and read ordering of ICacheWayLookup.

Each entry carries a unique ``pTag``. The reference model predicts residency;
the test proves that the queue returns exactly the entries written, in order,
and nothing else.
"""

from __future__ import annotations

import pytest

from icacheverify.waylookup.case.definitions import entry


@pytest.mark.feature("ICACHE-WAYLOOKUP-001")
async def test_single_entry_round_trip(waylookup_agent):
    agent = waylookup_agent
    payload = entry(0x0A5)

    agent.expect_empty()
    await agent.write(payload, ftq_value=1)
    assert agent.occupancy() == 1
    agent.expect_empty()

    beats = await agent.read_beats(1)
    assert len(beats) == 1
    assert beats[0].entry.ptag == payload.ptag
    assert agent.occupancy() == 0
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-001")
async def test_two_entries_return_in_write_order(waylookup_agent):
    agent = waylookup_agent
    first, second = entry(0x101), entry(0x202)

    await agent.write(first, ftq_value=2)
    await agent.write(second, ftq_value=2)
    assert agent.occupancy() == 2

    beats = await agent.read_beats(2)
    assert [beat.entry.ptag for beat in beats] == [first.ptag, second.ptag]
    assert agent.tags() == ()
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-002")
async def test_dual_port_write_enqueues_two_entries_at_once(waylookup_agent):
    agent = waylookup_agent
    first, second = entry(0x303), entry(0x404)

    await agent.write(first, second, ftq_value=3)
    assert agent.occupancy() == 2

    beats = await agent.read_beats(2)
    assert [beat.entry.ptag for beat in beats] == [first.ptag, second.ptag]
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-003")
async def test_queue_stops_accepting_at_the_port_reserve(waylookup_agent):
    """``write.ready = free >= FetchPorts`` reserves a dual-port slot.

    The probe against the RTL deasserts ready at occupancy ``depth - 1``, i.e.
    the queue always keeps one slot free even for single-port writes.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    payloads = []
    ftq = 0
    while agent.model.write_ready():
        payload = entry(0x1000 + ftq)
        await agent.write(payload, ftq_value=ftq % 64)
        payloads.append(payload)
        ftq += 1
        if ftq > depth:
            raise AssertionError("queue never deasserted write.ready")

    assert len(payloads) == depth - 1, f"accepted {len(payloads)} writes of {depth} slots"
    assert agent.occupancy() == depth - 1
    assert agent.model.write_ready() == 0, "queue must stop advertising ready at the reserve"

    beats = await agent.read_beats(len(payloads))
    assert [beat.entry.ptag for beat in beats] == [payload.ptag for payload in payloads]
    assert agent.occupancy() == 0
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-004")
async def test_flush_discards_everything(waylookup_agent):
    agent = waylookup_agent
    for index in range(4):
        await agent.write(entry(0x2000 + index), ftq_value=index)

    await agent.flush()
    assert agent.occupancy() == 0
    assert agent.tags() == ()
    agent.expect_empty()

    # A flushed queue must not emit stale data even with ready asserted.
    await agent.expect_no_read()


@pytest.mark.feature("ICACHE-WAYLOOKUP-007")
async def test_pointers_wrap_and_order_survives(waylookup_agent):
    """The queue is a ring buffer: the slot index must wrap, order must not.

    ``PrefetchDepth`` slots are addressed by a pointer plus a wrap flag, so
    after the write pointer passes the last slot it must continue at slot 0
    while the read side still returns the oldest entry first.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    first_batch = [entry(0x8000 + index) for index in range(depth - 12)]
    second_batch = [entry(0x8100 + index) for index in range(depth - 12)]

    for index, payload in enumerate(first_batch):
        await agent.write(payload, ftq_value=index % 64)
    # Advance the read pointer so the ring is no longer empty when it wraps.
    head = await agent.read_beats(10)
    assert [beat.entry.ptag for beat in head] == [payload.ptag for payload in first_batch[:10]]

    for offset, payload in enumerate(second_batch):
        await agent.write(payload, ftq_value=offset % 64)

    expected = [payload.ptag for payload in first_batch[10:]] + [
        payload.ptag for payload in second_batch]
    remaining = len(expected)
    assert agent.occupancy() == remaining
    assert agent.model.write_index() != 0, "the write pointer must have advanced past a slot wrap"

    beats = await agent.read_beats(remaining)
    assert [beat.entry.ptag for beat in beats] == expected
    assert agent.occupancy() == 0
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-010")
async def test_every_ring_slot_is_independent_storage(waylookup_agent):
    """Ring slots must not alias: each holds its own memo for both ports.

    A dual-port beat writes slot ``wp`` from port 0 and slot ``wp+1`` from port
    1, so reaching every slot through port 1 requires visiting every write
    pointer value. Alternating one dual and one single write advances the
    pointer by three and therefore sweeps all 32 residues
    (``gcd(3, 32) == 1``). Draining between sweeps keeps the queue under its
    port reserve.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    written: list[int] = []
    drained: list[int] = []
    counter = 0

    async def drain(count: int) -> None:
        nonlocal written, drained
        beats = await agent.read_beats(count)
        expected = written[len(drained):len(drained) + count]
        assert [beat.entry.ptag for beat in beats] == expected
        drained.extend(expected)

    for _ in range(depth):
        first, second = entry(0xA000 + counter), entry(0xA001 + counter)
        await agent.write(first, second, ftq_value=counter % 64)
        written += [first.ptag, second.ptag]
        counter += 2
        alone = entry(0xB000 + counter)
        await agent.write(alone, ftq_value=counter % 64)
        written.append(alone.ptag)
        counter += 1
        if len(written) - len(drained) >= 24:
            await drain(24)

    remaining = len(written) - len(drained)
    if remaining:
        await drain(remaining)
    assert agent.occupancy() == 0
    agent.expect_empty()
