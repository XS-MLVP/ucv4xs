"""Concurrent refill and prefetch write.

The prefetch write port and the refill update port are independent. When both
are active in the same cycle, the write must land in its own slot while the
refill corrects a *different* resident memo, and the refill must not be applied
to the entry being written in that same cycle (it is not cached yet).

Sweeping every write-pointer value while a refill is in flight also proves the
update path holds for every ring slot, not just the slot the pointer happens to
be at.
"""

from __future__ import annotations

import pytest

from icacheverify.waylookup.case.definitions import block
from icacheverify.waylookup.case.definitions import entry_for_block


@pytest.mark.feature("ICACHE-WAYLOOKUP-012")
async def test_refill_and_write_on_the_same_edge(waylookup_agent):
    agent = waylookup_agent
    victim_slot, written_slot = 3, 5
    victim_tag, written_tag = 0x2100, 0x2200
    victim_block = block(victim_tag, victim_slot)
    written_block = block(written_tag, written_slot)

    victim_entry = entry_for_block(victim_block, waymask=0b0001)
    await agent.write(victim_entry, ftq_value=1)

    new_entry = entry_for_block(written_block, waymask=0b0010)
    await agent.write_with_refill(
        new_entry,
        refill_block=victim_block,
        refill_waymask=0b1000,
        refill_rvc_map=0x3C,
        ftq_value=2,
    )

    memos = agent.resident(2)
    assert memos[0].waymask == 0b1000, "the resident memo must adopt the filled way"
    assert memos[0].maybe_rvc_map == 0x3C
    assert memos[1].waymask == 0b0010, "the newly written entry must keep its written way"

    beats = await agent.read_beats(2)
    assert [beat.entry.waymask[0] for beat in beats] == [0b1000, 0b0010]
    assert [beat.entry.ptag for beat in beats] == [victim_entry.ptag, new_entry.ptag]


@pytest.mark.feature("ICACHE-WAYLOOKUP-011")
async def test_update_path_holds_for_every_pointer_position(waylookup_agent):
    """Sweep all write-pointer values with a refill in flight each cycle.

    Each entry is written to the slot equal to its own set index, so a refill of
    a resident slot always matches exactly one memo. Two sweeps exercise the
    adopt (same tag) and invalidate (way taken by another tag) rules for every
    slot position.
    """
    agent = waylookup_agent
    depth = agent.model.depth
    # FIFO of (tag, waymask) in write order, mirroring the model's order list.
    queue: list[tuple[int, int]] = []
    tag = 0x3000

    async def sweep(*, rename_tag: bool) -> None:
        nonlocal tag
        for _ in range(depth):
            if len(queue) >= depth - 3:
                beats = await agent.read_beats(2)
                assert [b.entry.ptag for b in beats] == [t for t, _ in queue[:2]]
                del queue[:2]
            slot = agent.model.write_index()
            new_tag = tag
            tag += 1
            payload = entry_for_block(block(new_tag, slot), waymask=0b0001)
            new_ptag = payload.ptag
            # Refill a resident slot other than the one being written. Rotate
            # the target so every slot's inline update path is exercised, not
            # only the slot currently at the read pointer.
            read_slot = agent.model.read_index()
            target_index = None
            for delta in range(1, len(queue)):
                candidate = (slot + delta) % depth
                index = (candidate - read_slot) % depth
                if index < len(queue):
                    target_index = index
                    break
            if target_index is None:
                await agent.write(payload, ftq_value=new_tag % 64)
            else:
                target_tag, target_way = queue[target_index]
                target_slot = (read_slot + target_index) % depth
                # Recover the tag index that produced this pTag: block() builds
                # pTag as (tag_index << 2) | (set >> 6).
                tag_index = (target_tag >> 2) + (0x40 if rename_tag else 0)
                await agent.write_with_refill(
                    payload,
                    refill_block=block(tag_index, target_slot),
                    refill_waymask=target_way,
                    refill_rvc_map=0x20,
                    ftq_value=new_tag % 64,
                )
                queue[target_index] = (target_tag, 0 if rename_tag else target_way)
            queue.append((new_ptag, 0b0001))

    await sweep(rename_tag=False)   # adopt rule
    await sweep(rename_tag=True)    # invalidate rule
    remaining = len(queue)
    beats = await agent.read_beats(remaining)
    assert [b.entry.ptag for b in beats] == [t for t, _ in queue]
    agent.expect_empty()
