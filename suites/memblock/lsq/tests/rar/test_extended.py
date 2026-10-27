"""Native line gaps and observed semantic omissions drive these additional cases."""
import random

import pytest

from lsqverify.rar.types import Query, QueuePtr, Redirect, Release, RobPtr


def address(rank):
    # Consecutive small line tags have distinct 11-bit high folds. Expected
    # positive/negative assertions below do not call the model hash function.
    return (0x400 + rank) << 6


async def insert_records(env, records, *, lane=None):
    items = []
    width = 3 if lane is None else 1
    for start in range(0, len(records), width):
        group = records[start:start+width]
        queries = {(i if lane is None else lane): q for i, q in enumerate(group)}
        result = await env.cycle(queries)
        assert len(result.allocated) == len(group)
        items.extend(result.allocated)
    return tuple(items)


async def check_records(env, items, rob, expected=True):
    items = tuple(items)
    for start in range(0, len(items), 3):
        group = items[start:start+3]
        await env.probe(tuple(item.query.paddr for item in group), rob=rob, expect=(expected,) * len(group))


async def test_each_query_lane_owns_complete_pool_and_recycles(rar):
    env = rar
    for lane in range(3):
        head = env.head_input
        base = lane * 100
        records = [env.request(head + rank + 2, address(rank), rob=RobPtr.encode(base + rank + 2)) for rank in range(96)]
        items = await insert_records(env, records, lane=lane)
        assert env.observed.full
        await check_records(env, items, RobPtr.encode(base + 1))
        await env.advance_head(head + 97)
        await check_records(env, items, RobPtr.encode(base + 1), False)
        await env.settle_free()
        assert not env.model.entries and len(env.model.free.available) == 96 and not env.observed.full


async def test_full_pool_latter_rob_identity_and_high_address_recycle(rar):
    """Preserve latter ROB identities and high physical-address tags.

    All 96 real RAR entries are allocated through the public query ports with
    ``former=False`` and legal 48-bit addresses.  The independent model then
    checks the CAM responses before the architectural head retires every
    entry, proving that the high-address/latter identity is not lost before
    the actual free-pool return.
    """
    env = rar
    head = env.head_input
    records = [
        env.request(
            head + rank + 2,
            ((1 << 48) - 64 - rank * 64) & ~63,
            rob=RobPtr.encode(rank + 2, former=False),
            nc=True,
            data=True,
        )
        for rank in range(96)
    ]
    items = await insert_records(env, records)
    assert env.observed.full and len(items) == 96
    await check_records(env, items, RobPtr.encode(0, former=True))
    await env.advance_head(head + 98)
    await check_records(env, items, RobPtr.encode(0, former=True), expected=False)
    await env.settle_free()
    assert not env.model.entries and len(env.model.free.available) == 96


async def test_each_return_channel_accumulates_and_reuses_across_pool(rar):
    env = rar
    # Four full passes per channel move its return insertion across all
    # quarters of the actual circular pool. Each record is query-proven.
    for round_number, bank in enumerate(bank for bank in range(4) for _ in range(4)):
        head, base = env.head_input, round_number * 100
        expected_slots = tuple(env.model.free.available)
        old_rank, young_rank = 2, 74
        records = []
        for slot in expected_slots:
            rank = young_rank if slot % 4 == bank else old_rank
            if slot % 4 == bank:
                young_rank += 1
            else:
                old_rank += 1
            records.append(env.request(head + rank, address(rank), rob=RobPtr.encode(base + rank)))
        items = await insert_records(env, records)
        await check_records(env, items, RobPtr.encode(base + 1))
        doomed = tuple(item for item in items if item.slot % 4 == bank)
        survivors = tuple(item for item in items if item.slot % 4 != bank)
        result = await env.cycle(redirect=Redirect(True, RobPtr.encode(base + 73), False))
        assert {f.item.uid for f in result.freed} == {item.uid for item in doomed}
        await env.settle_free()
        await check_records(env, doomed, RobPtr.encode(base + 1), False)
        await check_records(env, survivors, RobPtr.encode(base + 1))
        replacements = [env.request(head + rank, address(rank), rob=RobPtr.encode(base + rank), nc=False, data=False)
                        for rank in range(74, 98)]
        new = await insert_records(env, replacements)
        await check_records(env, new, RobPtr.encode(base + 1), False)
        for item in new:
            await env.cycle(release=Release(True, item.query.paddr))
        await env.idle(2)
        await check_records(env, new, RobPtr.encode(base + 1))
        all_items = (*survivors, *new)
        await env.advance_head(head + 97)
        await check_records(env, all_items, RobPtr.encode(base + 1), False)
        await env.settle_free()
        assert len(env.model.free.available) == 96


@pytest.mark.parametrize("mode", ("concurrent", "previous"))
@pytest.mark.parametrize("data_valid", (True, False))
async def test_release_allocation_windows_and_data_valid(rar, mode, data_valid):
    env = rar
    a = address(0)
    if mode == "previous":
        await env.cycle(release=Release(True, a + 23))
    await env.cycle({1: env.request(2, a, nc=False, data=data_valid)},
                    release=Release(True, a + 41) if mode == "concurrent" else Release())
    await env.probe((a,), rob=RobPtr.encode(1), expect=(data_valid,))
    if not data_valid:
        # An allocated but unreleased record must later become observable,
        # so an always-empty implementation cannot pass the negative check.
        await env.cycle(release=Release(True, a))
        await env.probe((a,), rob=RobPtr.encode(1), expect=(False,))
        await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))
    await env.idle(4)
    await env.cycle(release=Release(True, address(99)))
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))


@pytest.mark.parametrize("mode", ("concurrent", "previous"))
async def test_hash_alias_is_not_full_line_in_allocation_window(rar, mode):
    env = rar
    a = address(0)
    b = a ^ (1 << 17) ^ (1 << 28)
    assert a >> 6 != b >> 6
    if mode == "previous":
        await env.cycle(release=Release(True, a))
    await env.cycle({2: env.request(2, b, nc=False, data=True)},
                    release=Release(True, a) if mode == "concurrent" else Release())
    await env.probe((b,), rob=RobPtr.encode(1), expect=(False,))
    await env.cycle(release=Release(True, b))
    await env.probe((b,), rob=RobPtr.encode(1), expect=(False,))
    await env.probe((b,), rob=RobPtr.encode(1), expect=(True,))
    # Existing-record CAM matching is deliberately conservative on this alias.
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))


async def test_line_offsets_address_bits_and_conservative_hash_collision(rar):
    env = rar
    a = 0x123456780000
    await env.cycle({0: env.request(2, a)})
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))
    for offset in (1, 2, 4, 8, 16, 32, 63):
        await env.probe((a + offset,), rob=RobPtr.encode(1), expect=(True,))
    for bit in range(6, 48):
        await env.probe((a, a ^ (1 << bit)), rob=RobPtr.encode(1), expect=(True, False))
    await env.probe((a ^ (1 << 17) ^ (1 << 28),), rob=RobPtr.encode(1), expect=(True,))


@pytest.mark.parametrize("stored_former", (False, True))
async def test_same_rob_entry_former_latter_and_non_younger_filters(rar, stored_former):
    env = rar
    a = address(0)
    stored = RobPtr.encode(10, former=stored_former)
    await env.cycle({1: env.request(2, a, rob=stored)})
    await env.probe((a,), rob=RobPtr.encode(10, former=not stored_former), expect=(not stored_former,))
    await env.probe((a,), rob=stored, expect=(False,))
    await env.probe((a,), rob=RobPtr.encode(11), expect=(False,))
    await env.probe((a,), rob=RobPtr.encode(9), expect=(True,))


@pytest.mark.parametrize("stored_entry,query_entry,wanted", ((160, 159, True), (159, 160, False)))
async def test_rob_wrap_does_not_sort_by_raw_value(rar, stored_entry, query_entry, wanted):
    a = address(0)
    await rar.cycle({2: rar.request(2, a, rob=RobPtr.encode(stored_entry))})
    await rar.probe((a,), rob=RobPtr.encode(query_entry), expect=(wanted,))
    await rar.probe((a,), rob=RobPtr.encode(stored_entry - 1), expect=(True,))


@pytest.mark.parametrize("older", (False, True))
async def test_revoke_history_and_old_state_query_response(rar, older):
    env = rar
    a = address(0)
    await env.cycle({0: env.request(2, a)})
    if older:
        await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))
    probe = Query(True, RobPtr.encode(1), QueuePtr.encode(env.head_input), a)
    kwargs = {"revoke_older" if older else "revoke_last": (0,)}
    await env.cycle({1: probe}, **kwargs)
    assert env.observed.responses[1].nuke  # old state, despite this edge's free
    await env.probe((a,), rob=RobPtr.encode(1), expect=(False,))
    await env.settle_free()


async def test_both_revoke_windows_and_new_allocation_overlap(rar):
    env = rar
    a, b, c = address(0), address(1), address(2)
    await env.cycle({0: env.request(2, a)})
    await env.cycle({0: env.request(3, b), 1: Query(True, RobPtr.encode(1), QueuePtr(), a)})
    assert env.observed.responses[1].nuke
    await env.cycle({0: env.request(4, c), 1: Query(True, RobPtr.encode(1), QueuePtr(), a),
                     2: Query(True, RobPtr.encode(1), QueuePtr(), b)}, revoke_last=(0,), revoke_older=(0,))
    assert env.observed.responses[1].nuke and env.observed.responses[2].nuke
    await env.probe((a, b, c), rob=RobPtr.encode(1), expect=(False, False, True))
    await env.settle_free()


async def test_fire_without_allocation_is_not_revoke_history(rar):
    env = rar
    a = address(0)
    await env.cycle({0: env.request(2, a)})
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))
    for kwargs in ({"revoke_last": (0,)}, {"revoke_older": (0,)}):
        await env.cycle({1: Query(True, RobPtr.encode(1), QueuePtr(), a)}, **kwargs)
        assert env.observed.responses[1].nuke
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))


async def test_multiple_matches_are_or_and_lanes_are_independent(rar):
    env = rar
    a = address(0)
    await env.cycle({0: env.request(2, a, rob=RobPtr.encode(2)), 1: env.request(3, a, rob=RobPtr.encode(3))})
    queries = {i: Query(True, RobPtr.encode(i + 1), QueuePtr(), a) for i in range(3)}
    await env.cycle(queries, revoke_last=(1,))
    assert tuple(r.nuke for r in env.observed.responses) == (True, True, False)
    await env.cycle({0: Query(True, RobPtr.encode(2), QueuePtr(), a), 1: Query(True, RobPtr.encode(1), QueuePtr(), a)})
    assert not env.observed.responses[0].nuke and env.observed.responses[1].nuke
    await env.settle_free()


async def test_sparse_need_and_canceled_queries_do_not_allocate(rar):
    env = rar
    a, b, c, d = (address(i) for i in range(4))
    result = await env.cycle({0: env.request(0, a, rob=RobPtr.encode(1)),
                              1: env.request(2, b, rob=RobPtr.encode(2)),
                              2: env.request(-1, c, rob=RobPtr.encode(0))})
    assert result.needed == (False, True, False) and len(result.allocated) == 1
    await env.probe((a, b, c), rob=RobPtr.encode(-1), expect=(False, True, False))
    await env.cycle({0: env.request(3, d, rob=RobPtr.encode(10))}, redirect=Redirect(True, RobPtr.encode(9), False))
    await env.probe((d,), rob=RobPtr.encode(8), expect=(False,))


async def test_three_causes_free_one_lifecycle_only_once(rar):
    env = rar
    a = address(0)
    await env.cycle({0: env.request(2, a, rob=RobPtr.encode(10))})
    result = await env.cycle({1: Query(True, RobPtr.encode(8), QueuePtr.encode(2), a)}, head=2,
                             redirect=Redirect(True, RobPtr.encode(9), False), revoke_last=(0,))
    assert len(result.freed) == 1 and len(result.freed[0].causes) == 3
    assert env.observed.responses[1].nuke
    await env.probe((a,), rob=RobPtr.encode(8), expect=(False,))
    await env.settle_free()
    assert len(env.model.free.available) == 96


@pytest.mark.parametrize("initial_free", (1, 2))
async def test_partial_capacity_nack_response_and_real_return_latency(rar, initial_free):
    env = rar
    count = 96 - initial_free
    records = [env.request(i + 2, address(i), rob=RobPtr.encode(i + 2)) for i in range(count)]
    items = await insert_records(env, records)
    await check_records(env, items, RobPtr.encode(1))
    new_queries = {i: env.request(count + i + 2, address(count + i), rob=RobPtr.encode(count + i + 2)) for i in range(3)}
    result = await env.cycle(new_queries)
    assert len(result.allocated) == initial_free
    ghosts = tuple(new_queries[i].paddr for i in range(initial_free, 3))
    await env.probe(ghosts, rob=RobPtr.encode(1), expect=(False,) * len(ghosts))
    await check_records(env, result.allocated, RobPtr.encode(1))
    # The older load in the reserved logical hole still queries while full.
    await env.cycle({0: env.request(1, address(0), rob=RobPtr.encode(1), nc=False)})
    assert not env.observed.ready[0] and env.observed.responses[0].valid and env.observed.responses[0].nuke

    pending = {i: env.request(100 + i, address(110 + i), rob=RobPtr.encode(100 + i)) for i in range(3)}
    freed = await env.cycle(pending, head=4)
    assert len(freed.freed) == 3 and env.observed.ready == (False, False, False)
    await env.cycle(pending)
    assert env.observed.ready == (False, False, False)
    await env.cycle(pending)
    assert env.observed.ready == (True, True, True)
    accepted = await env.cycle(pending)
    assert len(accepted.allocated) == 3
    await check_records(env, accepted.allocated, RobPtr.encode(1))
    await check_records(env, [f.item for f in freed.freed], RobPtr.encode(1), False)
    await env.advance_head(102)
    await env.settle_free()
    assert not env.observed.full and len(env.model.free.available) == 96


async def test_active_reset_and_disabled_inputs_do_not_leak_state(rar):
    env = rar
    a = address(0)
    await env.cycle({0: env.request(2, a)})
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))
    await env.cycle(release=Release(True, a))
    await env.reset()
    await env.probe((a,), rob=RobPtr.encode(1), expect=(False,))
    await env.cycle({2: env.request(2, a, nc=False, data=True)})
    for _ in range(4):
        queries = {i: Query(False, RobPtr.encode(159), QueuePtr(True, 119), address(i + 1), True, True) for i in range(3)}
        await env.cycle(queries, release=Release(False, a), redirect=Redirect(False, RobPtr.encode(0), True))
    await env.probe((a,), rob=RobPtr.encode(1), expect=(False,))
    await env.cycle(release=Release(True, a))
    await env.idle(1)
    await env.probe((a,), rob=RobPtr.encode(1), expect=(True,))


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_query_release_revoke_and_age_windows(rar, seed):
    env = rar
    rng = random.Random(seed)
    for cycle in range(1600):
        if cycle == 800:
            await env.reset()
        head = env.head_input + (rng.randrange(9) if rng.random() < 0.25 else 0)
        queries = {}
        for lane in range(3):
            if rng.random() < 0.65:
                position = head + rng.randrange(-1, 111)
                a = address(rng.randrange(96))
                if rng.random() < 0.1:
                    a ^= (1 << 17) | (1 << 28)
                queries[lane] = env.request(position, a, rob=RobPtr.encode(position), nc=rng.random() < 0.2, data=rng.random() < 0.7)
        entries = tuple(env.model.entries.values())
        release = Release(True, rng.choice(entries).query.paddr) if entries and rng.random() < 0.3 else Release()
        victim = rng.choice(entries) if entries and rng.random() < 0.06 else None
        redirect = Redirect(True, victim.query.rob, rng.random() < 0.5) if victim else Redirect()
        revoke_one = tuple(i for i in range(3) if rng.random() < 0.08)
        revoke_two = tuple(i for i in range(3) if rng.random() < 0.08)
        await env.cycle(queries, head=head, release=release, redirect=redirect, revoke_last=revoke_one, revoke_older=revoke_two)
    old = tuple(env.model.entries.values())
    await env.advance_head(max((item.lq_position for item in old), default=env.head_input))
    await env.settle_free()
    assert not env.model.entries and len(env.model.free.available) == 96
