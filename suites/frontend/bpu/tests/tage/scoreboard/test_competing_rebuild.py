"""An undefined competing rebuild must fail without consuming any learning."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.tage.model.semantic import Entry, Events, RecentLearning, TageReference, Write


def component_state(model):
    return deepcopy({name: ({key: vars(item) for key, item in value.items()}
                            if name in ('cache', 'useful_queue') else value)
                     for name, value in vars(model).items()})


def competing_requests():
    # A's original physical way differs from its current retained owner.
    # B is absent, so its own original counter proposes a complete rebuild.
    return (Write(37, 0, Entry(True, 101, 1), False),
            Write(37, 1, Entry(True, 103, 6), True))


def resident_cache(*, dirty=True):
    cache = RecentLearning()
    cache.advance(True, (Write(37, 1, Entry(True, 101, 2), False),))
    if not dirty:
        cache.advance(False)
    return cache


@pytest.mark.parametrize('busy', (False, True))
@pytest.mark.parametrize('dirty', (False, True), ids=('serviced', 'pending'))
@pytest.mark.parametrize('resident_first', (True, False), ids=('resident-first', 'rebuild-first'))
def test_undefined_competing_rebuild_does_not_partially_retire_or_learn(busy, dirty, resident_first):
    cache = resident_cache(dirty=dirty)
    requests = competing_requests()
    if not resident_first:
        requests = requests[::-1]
    before = deepcopy(vars(cache))
    with pytest.raises(ValueError, match='retained destination'):
        cache.advance(busy, requests)
    assert vars(cache) == before


def test_conflict_reports_both_logical_claims_and_the_current_resident():
    cache = resident_cache()
    with pytest.raises(ValueError, match='retained destination') as failure:
        cache.advance(True, competing_requests())
    assert failure.value.destination == (1, 0)
    assert failure.value.claims == competing_requests()
    assert failure.value.resident.write.entry == Entry(True, 101, 2)
    assert all(text in str(failure.value) for text in ('101', '103', 'owner=1', 'rank=0'))


@pytest.mark.parametrize('busy', (False, True))
def test_whole_tage_component_rejects_before_time_or_other_banks_advance(busy):
    model = TageReference()
    model.cache[3, 0] = resident_cache()
    model.cache[0, 0].advance(True, (Write(19, 0, Entry(True, 51, 4), True),))
    model.offers[3, 0] = competing_requests()
    before = component_state(model)
    with pytest.raises(ValueError, match='retained destination'):
        model.advance(Events(select=busy))
    assert component_state(model) == before


def test_not_ready_and_reset_do_not_consume_a_rejected_pending_boundary():
    model = TageReference()
    model.cache[3, 0] = resident_cache()
    model.offers[3, 0] = competing_requests()
    model.advance(Events(ready=False))
    assert model.cycles == 1
    assert model.cache[3, 0].find(37, 101).write.entry.counter == 2
    model.advance(Events(reset=True))
    assert not model.offers and model.cycles == 0
    assert all(not cache.records for cache in model.cache.values())


def test_independent_same_cycle_results_still_keep_both_complete_versions():
    cache = resident_cache()
    first, second = competing_requests()
    # B's owner is now distinct: both same-row results have enough resources.
    second = Write(second.row, 0, second.entry, second.taken)
    old = cache.advance(False, (first, second))
    assert len(old) == 1 and old[0].entry.counter == 2
    assert cache.find(37, 101).write.entry.counter == 1
    assert cache.find(37, 101).write.way == 1
    assert cache.find(37, 103).write.entry.counter == 6
    assert cache.find(37, 103).write.way == 0
    assert tuple(write.entry.counter for write in cache.advance(False)) == (6, 1)
