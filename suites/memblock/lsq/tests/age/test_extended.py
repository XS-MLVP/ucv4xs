"""The first pass already had 100% line coverage, but lacked 17 semantic cases."""
import random

import pytest


async def test_full_forty_reverse_shuffle_and_repeated_reuse(age):
    rng = random.Random(4040)
    shuffled = list(range(40))
    rng.shuffle(shuffled)
    for order in (tuple(reversed(range(40))), tuple(shuffled), tuple(range(40)), tuple(reversed(shuffled))):
        await age.insert_order(order, parallel=True)
        assert tuple(age.model.order) == order
        assert await age.drain() == order


async def test_sparse_enqueue_lanes_use_port_order_not_numeric_id(age):
    await age.cycle(enqueues=(None, 39, 2))
    await age.cycle(enqueues=(17, None, 1))
    await age.cycle(enqueues=(None, None, 36))
    assert await age.cycle(ready=(1, 2, 17, 36, 39)) == 39
    assert await age.cycle(ready=(1, 2, 17, 36)) == 2
    assert await age.cycle(ready=(1, 17, 36)) == 17
    assert await age.drain() == (39, 2, 17, 1, 36)


async def test_multiple_removal_preserves_survivors_and_full_rebuild(age):
    order = (8, 1, 35, 3, 39, 0, 17, 6, 37)
    await age.insert_order(order, parallel=True)
    removed = (8, 3, 17)
    survivors = tuple(item for item in order if item not in removed)
    assert await age.cycle(removes=removed, ready=survivors) == survivors[0]
    await age.cycle(enqueues=(17, 8, 3), ready=survivors)
    assert await age.drain() == (*survivors, 17, 8, 3)

    await age.insert_order(order, parallel=True)
    assert await age.cycle(removes=order) is None
    assert await age.cycle() is None
    await age.insert_order(reversed(order), parallel=True)
    assert await age.drain() == tuple(reversed(order))
    assert await age.cycle(removes=(5, 10, 32)) is None
    await age.cycle(enqueues=(15, 7, None))
    assert await age.cycle(removes=(0,), ready=(15, 7)) == 15
    assert await age.drain() == (15, 7)


async def test_same_cycle_remove_and_enqueue_deletion_has_priority(age):
    await age.insert_order((4, 17, 8, 39), parallel=True)
    assert await age.cycle(enqueues=(None, 4, 2), removes=(4, 8), ready=(17, 39)) == 17
    assert tuple(age.model.order) == (17, 39, 2)
    assert await age.cycle(ready=(17, 39, 2)) == 17
    await age.cycle(enqueues=(4, None, 8), ready=(17, 39, 2))
    assert await age.drain() == (17, 39, 2, 4, 8)


async def test_preedge_uses_current_age_then_reused_id_is_youngest(age):
    await age.insert_order((10, 2, 39), parallel=True)
    # Looking ahead through this beat's delete would incorrectly choose 2.
    assert await age.cycle(enqueues=(36, None, None), removes=(10,), ready=(10, 2, 39)) == 10
    assert await age.cycle(enqueues=(None, 10, None), ready=(2, 39, 36)) == 2
    assert await age.cycle(ready=(39, 10)) == 39
    assert await age.drain() == (2, 39, 36, 10)


async def test_reset_active_pool_rebuilds_different_age_relations(age):
    await age.insert_order(reversed(range(40)), parallel=True)
    assert await age.cycle(ready=range(40)) == 39
    await age.reset()
    new_order = (*range(0, 40, 2), *range(1, 40, 2))
    await age.insert_order(new_order, parallel=True)
    assert await age.drain() == new_order


async def test_each_eligible_pair_chooses_earlier_arrival(age):
    order = list(range(40))
    random.Random(1739).shuffle(order)
    await age.insert_order(order, parallel=True)
    # This is a semantic pairwise order check, not a copy of the RTL matrix.
    # Every comparison uses only two real eligible IDs and actual output.
    for i, older in enumerate(order):
        for younger in order[i + 1:]:
            assert await age.cycle(ready=(younger, older)) == older
    assert await age.drain() == tuple(order)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_live_set_and_ready_subsets(age, seed):
    rng = random.Random(seed)
    for _ in range(1600):
        live = tuple(age.model.order)
        removed = set(rng.sample(live, rng.randrange(min(len(live), 5) + 1))) if rng.random() < 0.5 else set()
        free = set(range(40)) - set(live)
        if free and rng.random() < 0.1:
            removed.add(rng.choice(sorted(free)))
        allowed_enqueues = sorted(free | removed)
        count = rng.randrange(min(3, len(allowed_enqueues)) + 1)
        incoming = rng.sample(allowed_enqueues, count)
        lanes = rng.sample(range(3), count)
        enqueues = [None, None, None]
        for lane, item in zip(lanes, incoming, strict=True):
            enqueues[lane] = item
        ready = rng.sample(live, rng.randrange(len(live) + 1))
        await age.cycle(enqueues=enqueues, removes=sorted(removed), ready=ready)
    expected = tuple(age.model.order)
    assert await age.drain() == expected
    # Reinsert every ID once after the stress phase to prove old removals and
    # the age of reused slots through real output, not just a cleared bitmap.
    order = list(range(40))
    rng.shuffle(order)
    await age.insert_order(order, parallel=True)
    assert await age.drain() == tuple(order)
