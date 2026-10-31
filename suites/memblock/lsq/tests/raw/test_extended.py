"""Real parent-block expansion driven by the first native line/semantic gaps."""
from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.raw.types import FtqPtr, Query, Redirect, RobPtr, SqPtr, Store


def address(rank):
    return 0x20000 + rank * 16


async def insert_records(env, records, *, lane=None):
    width = 3 if lane is None else 1
    items = []
    for start in range(0, len(records), width):
        group = records[start:start + width]
        result = await env.cycle({(i if lane is None else lane): query for i, query in enumerate(group)})
        assert len(result.allocated) == len(group)
        items.extend(result.allocated)
    return tuple(items)


async def check_records(env, items, rob, *, expected=True, both_ports=False):
    items = tuple(items)
    for start in range(0, len(items), 2):
        group = items[start:start + 2]
        permutations = (tuple(range(len(group))), tuple(reversed(range(len(group))))) if both_ports and len(group) == 2 else (tuple(range(len(group))),)
        for lanes in permutations:
            stores = {lane: env.store(item.query.paddr, rob=rob, tag=89 + lane) for lane, item in zip(lanes, group, strict=True)}
            await env.probe(stores, expect={lane: item.query if expected else None for lane, item in zip(lanes, group, strict=True)})


async def test_all_load_lanes_and_both_store_ports_cover_full_pool(raw):
    for lane in range(3):
        head, base = raw.head_input, lane * 72
        records = [raw.request(head + rank + 2, address(rank), rob=RobPtr.encode(base + rank + 2), tag=base + rank + 64)
                   for rank in range(56)]
        items = await insert_records(raw, records, lane=lane)
        assert raw.observed.full
        await check_records(raw, items, RobPtr.encode(base + 1), both_ports=True)
        await raw.advance_head(head + 57)
        await check_records(raw, items, RobPtr.encode(base + 1), expected=False)
        await raw.settle_free()
        assert not raw.model.entries and len(raw.model.free.available) == 56


async def test_each_return_channel_accumulates_and_wraps(raw):
    for round_number, bank in enumerate(bank for bank in range(4) for _ in range(4)):
        head, base = raw.head_input, round_number * 64
        older, younger = 2, 44
        records = []
        for slot in raw.model.free.available:
            rank = younger if slot % 4 == bank else older
            if slot % 4 == bank:
                younger += 1
            else:
                older += 1
            records.append(raw.request(head + rank, address(rank), rob=RobPtr.encode(base + rank), tag=base + rank))
        items = await insert_records(raw, records)
        await check_records(raw, items, RobPtr.encode(base + 1))
        doomed = tuple(item for item in items if item.slot % 4 == bank)
        survivors = tuple(item for item in items if item.slot % 4 != bank)
        result = await raw.cycle(redirect=Redirect(True, RobPtr.encode(base + 43), False))
        assert {f.item.uid for f in result.freed} == {item.uid for item in doomed}
        await raw.settle_free()
        await check_records(raw, doomed, RobPtr.encode(base + 1), expected=False)
        await check_records(raw, survivors, RobPtr.encode(base + 1))
        replacements = [raw.request(head + rank, address(rank), rob=RobPtr.encode(base + rank), tag=base + rank + 4096)
                        for rank in range(44, 58)]
        new = await insert_records(raw, replacements)
        await check_records(raw, new, RobPtr.encode(base + 1))
        await raw.advance_head(head + 57)
        await check_records(raw, (*survivors, *new), RobPtr.encode(base + 1), expected=False)
        await raw.settle_free()
        assert len(raw.model.free.available) == 56


async def test_word_line_offsets_and_each_address_bit(raw):
    a = 0x123456780000
    load = raw.request(2, a)
    await raw.cycle({0: load})
    for offset in range(16):
        await raw.probe((raw.store(a + offset, mask=1 << offset),), expect={0: load})
    for bit in range(4, 28):
        await raw.probe((raw.store(a ^ (1 << bit)),), expect={0: None})
    for bit in range(28, 48):
        await raw.probe((raw.store(a ^ (1 << bit)),), expect={0: load})
    for offset in (16, 32, 48):
        await raw.probe((raw.store(a + offset, wline=True),), expect={0: load})
    await raw.probe((raw.store(a + 64, wline=True),), expect={0: None})


async def test_all_byte_masks_zero_and_disjoint_even_for_wline(raw):
    for bit in range(16):
        a = address(bit * 4)
        load = raw.request(2 + bit, a, mask=1 << bit)
        await raw.cycle({bit % 3: load})
        await raw.probe((raw.store(a, mask=1 << bit),), expect={0: load})
        await raw.probe((raw.store(a, mask=1 << ((bit + 1) % 16)),), expect={0: None})
        await raw.probe((raw.store(a, mask=0),), expect={0: None})
        await raw.probe((raw.store(a + 16, mask=1 << ((bit + 1) % 16), wline=True),), expect={0: None})
    zero = raw.request(30, address(90), mask=0)
    await raw.cycle({1: zero})
    await raw.probe((raw.store(zero.paddr),), expect={0: None})


async def test_oldest_selection_is_not_arrival_or_physical_group_order(raw):
    common = address(100)
    records = [raw.request(8, common if rank % 8 == 0 else address(rank), rob=RobPtr.encode(57 - rank), tag=rank + 64)
               for rank in range(56)]
    await insert_records(raw, records)
    oldest = records[48]
    out = await raw.probe((raw.store(common, rob=RobPtr.encode(1)), raw.store(common, rob=RobPtr.encode(1), tag=94)),
                          expect={0: oldest, 1: oldest})
    assert out.training.ftq_value == oldest.ftq.value


@pytest.mark.parametrize("former", (False, True))
async def test_rob_same_entry_and_non_younger_filters(raw, former):
    load = raw.request(2, address(0), rob=RobPtr.encode(10, former=former))
    await raw.cycle({2: load})
    await raw.probe((raw.store(load.paddr, rob=load.rob),), expect={0: None})
    await raw.probe((raw.store(load.paddr, rob=RobPtr.encode(11)),), expect={0: None})
    await raw.probe((raw.store(load.paddr, rob=RobPtr.encode(10, former=not former)),), expect={0: load if not former else None})
    await raw.probe((raw.store(load.paddr, rob=RobPtr.encode(9)),), expect={0: load})


@pytest.mark.parametrize("entry,store_entry,wanted", ((160, 159, True), (159, 160, False)))
async def test_rob_wrap_has_logical_slot_age(raw, entry, store_entry, wanted):
    load = raw.request(2, address(0), rob=RobPtr.encode(entry))
    await raw.cycle({1: load})
    await raw.probe((raw.store(load.paddr, rob=RobPtr.encode(store_entry)),), expect={0: load if wanted else None})
    await raw.probe((raw.store(load.paddr, rob=RobPtr.encode(entry - 1)),), expect={0: load})


async def test_data_invalid_record_filtered_then_reuse_initializes_fresh(raw):
    # Fill the real pool: the invisible data-invalid record must consume a
    # real slot, so an implementation that ignores it cannot pass capacity.
    a = address(100)
    queries = [raw.request(i + 2, a if i < 2 else address(i), rob=RobPtr.encode(i + 2), data=i != 0) for i in range(56)]
    await insert_records(raw, queries)
    assert raw.observed.full
    await raw.probe((raw.store(a),), expect={0: queries[1]})
    await raw.advance_head(2)
    await raw.settle_free()
    replacement = raw.request(60, address(101), rob=RobPtr.encode(60), data=False)
    result = await raw.cycle({0: replacement})
    assert len(result.allocated) == 1 and raw.observed.full
    await raw.probe((raw.store(replacement.paddr),), expect={0: None})
    await raw.advance_head(60)
    await raw.settle_free()
    assert len(raw.model.free.available) == 56


async def test_two_store_routes_train_oldest_and_tie_prefers_lane_zero(raw):
    older = raw.request(2, address(0), rob=RobPtr.encode(10), tag=67)
    younger = raw.request(3, address(1), rob=RobPtr.encode(20), tag=94)
    await raw.cycle({0: older, 2: younger})
    out = await raw.probe((raw.store(younger.paddr, tag=121), raw.store(older.paddr, tag=78)), expect={0: younger, 1: older})
    assert out.training.ftq_value == older.ftq.value and out.training.store_ftq_value == 78 % 64
    out = await raw.probe((raw.store(older.paddr, tag=95), raw.store(older.paddr, tag=112)), expect={0: older, 1: older})
    assert out.training.store_ftq_value == 95 % 64 and out.training.store_ftq_offset == 95 * 3 % 32
    await raw.idle(3)


async def test_continuous_dual_store_metadata_and_tlb_miss(raw):
    loads = [raw.request(i + 2, address(i), rob=RobPtr.encode(i + 10), tag=i + 80) for i in range(2)]
    await raw.cycle({i: load for i, load in enumerate(loads)})
    for cycle in range(12):
        await raw.cycle(stores={i: raw.store(loads[(cycle + i) % 2].paddr, tag=cycle * 7 + i + 64) for i in range(2)})
        if cycle >= 2:
            for lane in range(2):
                expected = loads[(cycle - 2 + lane) % 2]
                assert raw.observed.rollbacks[lane].rob == expected.rob
                assert raw.observed.rollbacks[lane].store_ftq_value == ((cycle - 2) * 7 + lane + 64) % 64
    await raw.idle(4)
    out = await raw.probe((raw.store(loads[0].paddr, tlb_miss=True, tag=95), raw.store(loads[1].paddr, tag=100)),
                          expect={0: None, 1: loads[1]})
    assert out.training.ftq_value == loads[1].ftq.value
    await raw.probe((raw.store(loads[0].paddr, tlb_miss=True),), expect={0: None})
    await raw.idle(4)


@pytest.mark.parametrize("stage", (0, 1, 2))
async def test_redirect_at_each_selection_stage_preserves_survivor(raw, stage):
    loads = [raw.request(i + 2, address(i), rob=RobPtr.encode(5 + i * 5)) for i in range(3)]
    items = await insert_records(raw, loads)
    await check_records(raw, items, RobPtr.encode(1))
    redirect = Redirect(True, RobPtr.encode(9), False)
    await raw.cycle(stores={1: raw.store(loads[1].paddr)}, redirect=redirect if stage == 0 else Redirect())
    for current in (1, 2):
        await raw.cycle(redirect=redirect if current == stage else Redirect())
    assert not raw.observed.rollbacks[1].valid
    await raw.probe((raw.store(loads[1].paddr), raw.store(loads[0].paddr)), expect={0: None, 1: loads[0]})
    # A surviving load still participates when redirect is concurrent with
    # the store source edge; don't implement cancellation as global mute.
    await raw.cycle(stores={0: raw.store(loads[0].paddr)}, redirect=Redirect(True, RobPtr.encode(6), False))
    await raw.idle(2)
    assert raw.observed.rollbacks[0].valid
    await raw.settle_free()


@pytest.mark.parametrize("flush_self", (False, True))
async def test_redirect_flush_self_and_same_slot_boundary(raw, flush_self):
    load = raw.request(2, address(0), rob=RobPtr.encode(10, former=True))
    await raw.cycle({0: load})
    await raw.probe((raw.store(load.paddr),), expect={0: load})
    await raw.cycle(redirect=Redirect(True, load.rob, flush_self))
    await raw.probe((raw.store(load.paddr),), expect={0: None if flush_self else load})
    await raw.settle_free()


async def test_two_cycle_revoke_and_later_revoke_keeps_old_store_snapshot(raw):
    load = raw.request(2, address(0))
    await raw.cycle({2: load})
    await raw.cycle(stores={0: raw.store(load.paddr)})
    # It is too late to add revoke filtering to the already captured store.
    await raw.cycle(revoke_older=(2,))
    await raw.cycle()
    assert raw.observed.rollbacks[0].valid
    await raw.probe((raw.store(load.paddr),), expect={0: None})
    await raw.settle_free()


async def test_revoke_fire_without_allocation_does_not_delete_old_record(raw):
    load = raw.request(2, address(0))
    await raw.cycle({0: load})
    await raw.probe((raw.store(load.paddr),), expect={0: load})
    no_alloc = raw.request(0, address(1), rob=RobPtr.encode(3))
    await raw.cycle({0: no_alloc})
    await raw.cycle(revoke_last=(0,), stores={0: raw.store(load.paddr), 1: raw.store(no_alloc.paddr)})
    await raw.cycle(revoke_older=(0,))
    await raw.idle(1)
    assert raw.observed.rollbacks[0].valid and not raw.observed.rollbacks[1].valid
    await raw.probe((raw.store(load.paddr),), expect={0: load})


@pytest.mark.parametrize("both", (False, True))
async def test_revoke_from_full_pool_has_exact_capacity_and_fresh_identity(raw, both):
    count = 54 if both else 55
    queries = [raw.request(i + 2, address(i), rob=RobPtr.encode(i + 2)) for i in range(count)]
    items = list(await insert_records(raw, queries))
    await check_records(raw, items, RobPtr.encode(1))
    older = None
    if both:
        older = raw.request(56, address(54), rob=RobPtr.encode(56))
        items.extend((await raw.cycle({2: older})).allocated)
    newest = raw.request(57, address(55), rob=RobPtr.encode(57))
    result = await raw.cycle({2: newest}, stores={0: raw.store(older.paddr)} if older else ())
    items.extend(result.allocated)
    assert raw.observed.full
    victims = (older, newest) if older else (newest,)
    await raw.cycle(revoke_last=(2,), revoke_older=(2,) if both else (),
                    stores={i: raw.store(query.paddr) for i, query in enumerate(victims)})
    await raw.idle(2)
    assert not any(rb.valid for rb in raw.observed.rollbacks)
    await raw.settle_free()
    assert len(raw.model.free.available) == len(victims)
    replacements = [raw.request(60 + i, address(100 + i), rob=RobPtr.encode(60 + i), tag=99 + i) for i in range(len(victims))]
    new = await insert_records(raw, replacements)
    assert raw.observed.full
    await check_records(raw, new, RobPtr.encode(1))
    await raw.probe({i: raw.store(query.paddr) for i, query in enumerate(victims)}, expect={i: None for i in range(len(victims))})
    await check_records(raw, items[:-len(victims)], RobPtr.encode(1))
    await raw.advance_head(61)
    await raw.settle_free()
    assert len(raw.model.free.available) == 56


async def test_sparse_need_and_redirect_canceled_load_do_not_allocate(raw):
    loads = [raw.request(position, address(i), rob=RobPtr.encode(2 + i)) for i, position in enumerate((0, 2, -1))]
    result = await raw.cycle(dict(enumerate(loads)))
    assert result.needed == (False, True, False)
    # Immediate next source edge is required to expose an erroneous hidden
    # allocation before the ready pointer could automatically clear it.
    await raw.cycle(stores={0: raw.store(loads[0].paddr), 1: raw.store(loads[2].paddr)})
    await raw.idle(2)
    assert not any(rb.valid for rb in raw.observed.rollbacks)
    await raw.probe((raw.store(loads[1].paddr),), expect={0: loads[1]})
    canceled = raw.request(3, address(3), rob=RobPtr.encode(10))
    await raw.cycle({2: canceled}, redirect=Redirect(True, RobPtr.encode(9), False))
    await raw.probe((raw.store(canceled.paddr),), expect={0: None})


@pytest.mark.parametrize("initial_free", (1, 2))
async def test_partial_capacity_nack_then_return_and_prefetch_wait(raw, initial_free):
    count = 56 - initial_free
    records = [raw.request(i + 2, address(i), rob=RobPtr.encode(i + 2)) for i in range(count)]
    items = await insert_records(raw, records)
    await check_records(raw, items, RobPtr.encode(1))
    queries = {lane: raw.request(count + lane + 2, address(count + lane), rob=RobPtr.encode(count + lane + 2)) for lane in range(3)}
    result = await raw.cycle(queries)
    assert len(result.allocated) == initial_free
    ghosts = [query for lane, query in queries.items() if lane >= initial_free]
    await raw.probe({i: raw.store(query.paddr) for i, query in enumerate(ghosts)}, expect={i: None for i in range(len(ghosts))})
    await check_records(raw, result.allocated, RobPtr.encode(1))
    pending = {lane: raw.request(60 + lane, address(100 + lane), rob=RobPtr.encode(60 + lane)) for lane in range(3)}
    change = await raw.cycle(pending, head=4)
    assert len(change.freed) == 3 and raw.observed.full and raw.observed.ready == (False, False, False)
    await raw.cycle(pending)
    assert raw.observed.full and raw.observed.ready == (False, False, False)
    await raw.cycle(pending)
    assert not raw.observed.full and raw.observed.ready == (False, False, False)
    await raw.cycle(pending)
    assert raw.observed.ready == (True, True, True)
    allocated = await raw.cycle(pending)
    assert len(allocated.allocated) == 3 and raw.observed.full
    await check_records(raw, allocated.allocated, RobPtr.encode(1))
    await check_records(raw, [f.item for f in change.freed], RobPtr.encode(1), expected=False)
    await raw.advance_head(62)
    await raw.settle_free()
    assert len(raw.model.free.available) == 56


async def test_multiple_free_causes_and_old_head_snapshot(raw):
    load = raw.request(2, address(0), rob=RobPtr.encode(10))
    await raw.cycle({0: load})
    await raw.cycle(stores={0: raw.store(load.paddr)})
    result = await raw.cycle(head=2, redirect=Redirect(True, RobPtr.encode(9), False), revoke_older=(0,))
    assert len(result.freed) == 1 and len(result.freed[0].causes) == 3
    await raw.idle(1)  # redirect correctly cancels the older captured job
    assert not raw.observed.rollbacks[0].valid
    await raw.probe((raw.store(load.paddr),), expect={0: None})
    await raw.settle_free()
    # A head movement alone is not a filter in the source-cycle candidate
    # snapshot. This second record must still report that same-edge store.
    other = raw.request(4, address(1), rob=RobPtr.encode(11))
    await raw.cycle({1: other})
    await raw.cycle(stores={0: raw.store(other.paddr)}, head=4)
    await raw.idle(2)
    assert raw.observed.rollbacks[0].valid
    await raw.probe((raw.store(other.paddr),), expect={0: None})
    await raw.settle_free()
    proven = raw.request(6, address(2), rob=RobPtr.encode(12))
    await raw.cycle({2: proven})
    await raw.probe((raw.store(proven.paddr),), expect={0: proven})
    result = await raw.cycle(head=6, redirect=Redirect(True, RobPtr.encode(11), False))
    assert len(result.freed) == 1 and len(result.freed[0].causes) == 2
    await raw.probe((raw.store(proven.paddr),), expect={0: None})
    await raw.settle_free()


async def test_same_edge_new_record_not_visible_but_next_store_is(raw):
    load = raw.request(2, address(0))
    await raw.cycle({2: load}, stores={1: raw.store(load.paddr)})
    await raw.cycle(stores={1: raw.store(load.paddr, tag=88)})
    await raw.cycle()
    assert not raw.observed.rollbacks[1].valid
    await raw.cycle()
    assert raw.observed.rollbacks[1].valid and raw.observed.rollbacks[1].store_ftq_value == 88 % 64


async def test_active_inflight_reset_and_disabled_payloads(raw):
    load = raw.request(2, address(0))
    await raw.cycle({0: load})
    await raw.probe((raw.store(load.paddr),), expect={0: load})
    await raw.cycle(stores={0: raw.store(load.paddr)})
    await raw.reset()
    await raw.probe((raw.store(load.paddr),), expect={0: None})
    for _ in range(4):
        await raw.cycle({i: Query(False, RobPtr.encode(159), SqPtr(True, True, 63), address(i), 0xFFFF, True, True,
                                  FtqPtr(True, 63), 31, (1 << 64) - 1) for i in range(3)},
                        stores={i: replace(raw.store(load.paddr, tlb_miss=True), valid=False) for i in range(2)},
                        redirect=Redirect(False, RobPtr.encode(0), True))
    await raw.probe((raw.store(load.paddr),), expect={0: None})
    newer = raw.request(2, load.paddr, tag=102)
    await raw.cycle({1: newer})
    await raw.probe((raw.store(newer.paddr),), expect={0: newer})


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_concurrent_queries_stores_and_recovery(raw, seed):
    rng = random.Random(seed)
    for cycle in range(1600):
        if cycle == 800:
            await raw.reset()
        head = raw.head_input + (rng.randrange(9) if rng.random() < 0.24 else 0)
        queries = {}
        for lane in range(3):
            if rng.random() < 0.65:
                position = head + rng.randrange(-1, 111)
                queries[lane] = raw.request(position, address(rng.randrange(32)), rob=RobPtr.encode(position, former=lane != 2),
                                             mask=rng.randrange(1 << 16), data=rng.random() < 0.8, tag=2 * position + int(lane == 2))
        stores = {}
        for lane in range(2):
            if rng.random() < 0.6:
                entry = head + rng.randrange(-2, 105)
                stores[lane] = raw.store(address(rng.randrange(32)), rob=RobPtr.encode(entry),
                                         mask=rng.randrange(1 << 16), wline=rng.random() < 0.1,
                                         tlb_miss=rng.random() < 0.08, tag=2 * entry + 1)
        entries = tuple(raw.model.entries.values())
        victim = rng.choice(entries) if entries and rng.random() < 0.04 else None
        redirect = Redirect(True, victim.query.rob, rng.random() < 0.5) if victim else Redirect()
        await raw.cycle(queries, stores=stores, head=head, redirect=redirect,
                        revoke_last=tuple(i for i in range(3) if rng.random() < 0.06),
                        revoke_older=tuple(i for i in range(3) if rng.random() < 0.06))
    old = tuple(raw.model.entries.values())
    await raw.advance_head(max((item.sq_position for item in old), default=raw.head_input))
    await raw.settle_free()
    assert not raw.model.entries and not raw.model.pending and len(raw.model.free.available) == 56
