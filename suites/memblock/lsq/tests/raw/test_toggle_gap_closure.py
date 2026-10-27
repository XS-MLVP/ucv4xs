"""Legal full-width RAW payload case for address/checkpoint transitions."""

from dataclasses import replace

from lsqverify.raw.types import RobPtr


async def test_full_width_checkpoint_and_physical_address_payload(raw):
    address = (1 << 48) - 16
    load = replace(
        raw.request(2, address, rob=RobPtr.encode(64, former=False), mask=0xA55A, tag=0x155),
        checkpoint=(1 << 64) - 1,
    )
    await raw.cycle({0: load})
    store = replace(
        raw.store(address, rob=RobPtr.encode(63), mask=0x5A5A, wline=True, tag=0x1A5),
    )
    await raw.probe((store,), expect={0: load})

    # The second transaction returns the public payload fields to a legal
    # low-valued pattern; the independent model still checks the same oldest
    # conflict and full rollback metadata rather than reading DUT state.
    low = replace(raw.request(3, 0, rob=RobPtr.encode(65), mask=1, tag=0), checkpoint=0)
    await raw.cycle({1: low})
    await raw.probe((raw.store(0, rob=RobPtr.encode(64), mask=1, tag=0),), expect={0: low})


async def test_full_pool_runahead_checkpoint_bits_survive_reuse(raw):
    """Drive every real RAW slot with legal high/low checkpoint payloads.

    The checkpoint is a public uop field, so this reaches the stored
    ``runahead_checkpoint_id`` bits through the normal query/allocate path.
    The second lifetime reuses the same physical pool with the opposite
    payload and checks the delayed rollback through the independent model.
    """

    async def allocate_pool(checkpoint, rob_base, address_base):
        head = raw.head_input
        queries = []
        for slot in range(56):
            query = raw.request(
                head + slot + 2,
                address_base + slot * 16,
                rob=RobPtr.encode(rob_base + slot),
                tag=rob_base + slot + 64,
            )
            queries.append(replace(query, checkpoint=checkpoint))

        items = []
        for start in range(0, len(queries), 3):
            group = queries[start:start + 3]
            change = await raw.cycle({lane: query for lane, query in enumerate(group)})
            assert len(change.allocated) == len(group)
            items.extend(change.allocated)
        assert raw.observed.full and len(items) == 56

        for start in range(0, len(queries), 2):
            group = queries[start:start + 2]
            await raw.probe(
                {lane: raw.store(query.paddr, rob=RobPtr.encode(1), tag=128 + lane)
                 for lane, query in enumerate(group)},
                expect={lane: query for lane, query in enumerate(group)},
            )
        return head, queries

    high = (1 << 64) - 1
    first_head, _ = await allocate_pool(high, 2, 0x400000)
    await raw.advance_head(first_head + 57)
    await raw.settle_free()
    assert len(raw.model.free.available) == 56

    second_head, _ = await allocate_pool(0, 100, 0x500000)
    await raw.advance_head(second_head + 57)
    await raw.settle_free()
    assert len(raw.model.free.available) == 56
