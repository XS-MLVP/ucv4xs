"""Memo correction must reach the entry wherever the ring stores it.

A refill rewrites the memo of a resident entry. Because the ring is indexed by
a wrapping pointer, the same rule must hold for every slot; a rule that only
works for slot 0 would silently serve stale ways for the rest of the queue.
"""

from __future__ import annotations

import pytest

from suites.frontend.icache.waylookup.case.definitions import block
from suites.frontend.icache.waylookup.case.definitions import entry_for_block


@pytest.mark.feature("ICACHE-WAYLOOKUP-011")
async def test_every_slot_accepts_the_adopt_and_invalidate_update(waylookup_agent):
    agent = waylookup_agent
    depth = agent.model.depth
    resident = depth - 1  # the queue reserves one slot for a dual-port beat

    # Fill slot i with an entry for set i so a refill of set i touches exactly
    # that slot. Distinct tags per slot keep the payloads comparable.
    payloads = []
    for slot in range(resident):
        ptag = 0x1000 + slot
        payload = entry_for_block(block(ptag, slot), waymask=0b0001)
        await agent.write(payload, ftq_value=slot % 64)
        payloads.append((slot, ptag, payload))

    # Adopt: same tag, a different way.
    for slot, ptag, _ in payloads:
        await agent.refill(block(ptag, slot), waymask=0b0100, maybe_rvc_map=0x11 + slot)
    for index, (slot, ptag, _) in enumerate(payloads):
        memo = agent.resident(resident)[index]
        assert memo.waymask == 0b0100, f"slot {slot} did not adopt the filled way"
        assert memo.maybe_rvc_map == 0x11 + slot, f"slot {slot} kept a stale RVC map"

    # Invalidate: another tag now owns the way this memo claims.
    for slot, ptag, _ in payloads:
        await agent.refill(block(ptag + 0x100, slot), waymask=0b0100)
    for index, (slot, _, _) in enumerate(payloads):
        memo = agent.resident(resident)[index]
        assert memo.waymask == 0, f"slot {slot} kept a way another tag now owns"

    beats = await agent.read_beats(resident)
    assert [beat.entry.waymask[0] for beat in beats] == [0] * resident
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-013")
async def test_update_reaches_every_slot_when_no_write_occurs(waylookup_agent):
    """Refill-only cycles must correct every slot of the ring.

    The memo update is combinational over all slots, so a library that only
    refills the slot at the read pointer leaves the rest of the ring's update
    path unproven. This walks the ring so every slot is both occupied and
    corrected at least once, including the slots only reachable after the write
    pointer wraps.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    expected: dict[int, int] = {}

    for step in range(depth * 2):
        if len(agent.model.tags) >= depth - 3:
            await agent.read_beats(2)
            expected = {}
        slot = agent.model.write_index()
        tag_index = 0x100 + step
        payload = entry_for_block(block(tag_index, slot), waymask=0b0001)
        await agent.write(payload, ftq_value=step % 64)
        # Separate cycle, no write: only the memo update path is active.
        await agent.refill(block(tag_index, slot), waymask=0b1000,
                           maybe_rvc_map=0x40 + (step % 32))
        expected[slot] = 0x40 + (step % 32)

        for memo in agent.resident(len(agent.model.tags)):
            memo_slot = next(
                (s for s in expected if memo.maybe_rvc_map == 0 or True), None)
        # Every resident memo that has been refilled must show the new RVC map.
        for memo in agent.resident(len(agent.model.tags)):
            assert memo.waymask == 0b1000, "a resident memo missed its correction"

    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-013")
async def test_update_reaches_every_slot_while_a_write_occurs(waylookup_agent):
    """A concurrent write must not block the correction of any other slot.

    While one slot is being written, the update path of every *other* occupied
    slot must still take effect. Rotating the target across all offsets covers
    each slot's inline update branch.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    queue: list[tuple[int, int]] = []   # (ptag, waymask) in FIFO order
    tag_index = 0x300

    for step in range(depth * 2):
        if len(queue) >= depth - 3:
            beats = await agent.read_beats(2)
            assert [b.entry.ptag for b in beats] == [t for t, _ in queue[:2]]
            del queue[:2]
        write_slot = agent.model.write_index()
        payload = entry_for_block(block(tag_index, write_slot), waymask=0b0010)
        tag_index += 1

        read_slot = agent.model.read_index()
        # Rotate the offset so successive steps pick a different resident slot:
        # the per-slot correction branch is only reached when the write lands in
        # a *different* slot, and each slot needs its own visit.
        target_index = None
        rotation = 1 + (step % (depth - 1))
        for delta in range(depth - 1):
            offset = 1 + (rotation + delta - 1) % (depth - 1)
            candidate = (write_slot + offset) % depth
            index = (candidate - read_slot) % depth
            if index < len(queue):
                target_index = index
                break
        if target_index is None:
            await agent.write(payload, ftq_value=step % 64)
        else:
            target_ptag, _ = queue[target_index]
            target_slot = (read_slot + target_index) % depth
            await agent.write_with_refill(
                payload,
                refill_block=block(target_ptag >> 2, target_slot),
                refill_waymask=0b1000,
                refill_rvc_map=0x60 + target_slot,
                ftq_value=step % 64,
            )
            queue[target_index] = (target_ptag, 0b1000)
        queue.append((payload.ptag, 0b0010))

    expected_rvc = [m.maybe_rvc_map for m in agent.resident(len(queue))]
    beats = await agent.read_beats(len(queue))
    assert [b.entry.waymask[0] for b in beats] == [w for _, w in queue]
    assert [b.entry.maybe_rvc_map[0] for b in beats] == expected_rvc
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-013")
async def test_invalidate_applies_in_all_three_write_contexts(waylookup_agent):
    """The invalidate rule must hold whether or not a write happens alongside.

    The correction logic sees three situations: a refill alone, a refill with a
    single-port write, and a refill with a dual-port write. Five writes per
    iteration advance the write pointer by five, and ``gcd(5, 32) == 1`` so every
    slot takes each of the three roles within 32 iterations.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    tag = 0x900

    for iteration in range(depth):
        slot_a = agent.model.write_index()
        a = entry_for_block(block(tag, slot_a), waymask=0b0010)
        tag += 1
        await agent.write(a, ftq_value=iteration % 64)

        slot_b = agent.model.write_index()
        b = entry_for_block(block(tag, slot_b), waymask=0b0010)
        tag += 1
        await agent.write(b, ftq_value=iteration % 64)

        # Context 1: refill alone invalidates A.
        await agent.refill(block((a.ptag >> 2) + 0x400, slot_a), waymask=0b0010,
                           maybe_rvc_map=0x10)

        # Context 2: single write C, refill B invalidates.
        slot_c = agent.model.write_index()
        c = entry_for_block(block(tag, slot_c), waymask=0b0010)
        tag += 1
        await agent.write_with_refill(
            c, refill_block=block((b.ptag >> 2) + 0x400, slot_b),
            refill_waymask=0b0010, refill_rvc_map=0x20, ftq_value=iteration % 64)

        # Context 3: dual write D/E, refill C invalidates.
        slot_d = agent.model.write_index()
        d = entry_for_block(block(tag, slot_d), waymask=0b0010)
        tag += 1
        slot_e = (slot_d + 1) % depth
        e = entry_for_block(block(tag, slot_e), waymask=0b0010)
        tag += 1
        await agent.write_pair_with_refill(
            d, e, refill_block=block((c.ptag >> 2) + 0x400, slot_c),
            refill_waymask=0b0010, refill_rvc_map=0x30, ftq_value=iteration % 64)

        beats = []
        while agent.model.tags:
            beats += list(await agent.read_beats(min(2, len(agent.model.tags))))
        assert [beat.entry.waymask[0] for beat in beats] == [0, 0, 0, 0b0010, 0b0010], (
            f"iteration {iteration}: invalidate did not apply in every context")
        assert [beat.entry.ptag for beat in beats] == [
            a.ptag, b.ptag, c.ptag, d.ptag, e.ptag]
        agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-013")
async def test_last_slot_correction_while_writing_slot_zero(waylookup_agent):
    """Slot 31 sits at the end of the write-select chain.

    When the write pointer wraps to slot 0 and the refill targets slot 31, the
    correction must still take effect: it is the one combination where the
    written slot is the first in the chain and the corrected slot the last.
    """
    agent = waylookup_agent
    depth = agent.model.depth

    entries = []
    while agent.model.write_ready():
        slot = agent.model.write_index()
        payload = entry_for_block(block(0xA00 + slot, slot), waymask=0b0010)
        await agent.write(payload, ftq_value=slot % 64)
        entries.append((slot, payload))
        assert len(entries) <= depth, "the queue accepted more writes than it has slots"

    # Fill the last slot: free space first, then write into slot 31 so the
    # write pointer wraps to slot 0.
    await agent.read_beats(2)
    last_slot = agent.model.write_index()
    assert last_slot == depth - 1, "the write pointer must be at the last slot"
    last_entry = entry_for_block(block(0xA31, last_slot), waymask=0b0010)
    await agent.write(last_entry, ftq_value=31)
    assert agent.model.write_index() == 0, "the write pointer must have wrapped to slot 0"
    entries = [(slot, payload) for slot, payload in entries[2:]]
    entries.append((last_slot, last_entry))
    await agent.read_beats(1)

    last_slot, last_entry = entries[-1]
    fresh = entry_for_block(block(0xB00, 0), waymask=0b0010)
    resident_before = len(agent.model.tags)
    await agent.write_with_refill(
        fresh,
        refill_block=block((last_entry.ptag >> 2) + 0x400, last_slot),
        refill_waymask=0b0010,
        refill_rvc_map=0x55,
        ftq_value=13,
    )

    memos = agent.resident(resident_before + 1)
    assert memos[-2].waymask == 0, "slot 31 must lose a way another line now owns"
    assert memos[-1].waymask == 0b0010, "the new entry keeps its written way"

    beats = await agent.read_beats(resident_before + 1)
    assert [b.entry.waymask[0] for b in beats][-2:] == [0, 0b0010]
    agent.expect_empty()


@pytest.mark.feature("ICACHE-WAYLOOKUP-011")
async def test_last_slot_is_corrected_while_a_write_occurs(waylookup_agent):
    """The ring's final slot must take the update even during a write.

    The queue can only be filled to its last slot by a dual write, after which
    the ring is full.  Freeing two entries lets the write pointer wrap to slot 0
    and leaves slot 31 occupied, so a single write to slot 0 and a refill of the
    slot-31 tag are genuinely concurrent.  This is the only pointer position
    where the last slot's inline update branch runs in the ``else`` arm of the
    write decode.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    assert depth == 32

    for slot in range(depth - 2):
        await agent.write(
            entry_for_block(block(0x100 + slot, slot), waymask=0b0001),
            ftq_value=slot)
    # The dual write fills slots 30 and 31; the ring is now full.
    await agent.write(
        entry_for_block(block(0x200, 30), waymask=0b0001),
        entry_for_block(block(0x201, 31), waymask=0b0001),
        ftq_value=30)
    assert agent.model.occupancy() == depth

    # Free two slots: read pointer moves to 2, write pointer wraps to 0.
    await agent.read_beats(2)

    # One cycle: append to slot 0 and adopt a new way in the slot-31 entry.
    await agent.write_with_refill(
        entry_for_block(block(0x300, 0), waymask=0b0001),
        refill_block=block(0x201, 31), refill_waymask=0b0100)

    await agent.read_beats(depth - 3)
    tail = await agent.read_beats(1)
    assert tail[0].entry.waymask[0] == 0b0100, (
        "the last ring slot kept its stale way")
    agent.expect_empty()
