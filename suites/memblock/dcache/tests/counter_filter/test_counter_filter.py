"""CounterFilter UT: FIFO residency, query matching and capacity/wrap."""
from __future__ import annotations

import random

import pytest

from dcacheverify.counter_filter.coverage import CounterFilterCoverage
from dcacheverify.counter_filter.env import CounterFilterEnv
from dcacheverify.counter_filter.model import SIZE

NONE = None


@pytest.fixture
def cf(dut_factory):
    dut = dut_factory("counter_filter")
    return CounterFilterEnv(dut, CounterFilterCoverage())


def loads(*entries):
    values = list(entries)
    while len(values) < 3:
        values.append(None)
    return values


def queries(*entries):
    values = list(entries)
    while len(values) < 3:
        values.append(None)
    return values


# CF-FP-001, CF-FP-003
def test_reset_empty_and_invalid_queries(cf):
    cf.reset()
    # Invalid queries return zero even for lines that will later be stored.
    cf.step(loads(), queries((0, 0, False), (0, 0, False), (0, 0, False)))
    # Misses across the index/way space and all three query ports.
    for idx in (0, 1, 127, 128, 254, 255):
        for way in range(4):
            hits = cf.step(
                loads(), queries((idx, way, True), (idx, (way + 1) & 3, True),
                                (idx, (way + 2) & 3, True)))
            assert hits == [False, False, False]
    assert cf.model.occupancy == 0


# CF-FP-002, CF-FP-004
def test_single_entry_lifetime(cf):
    cf.reset()
    # The entry is invisible in the enqueue cycle itself.
    hits = cf.step(loads((10, 2)), queries((10, 2, True), None, None))
    assert hits[0] is False
    # Visible for four consecutive cycles (age 0..3).
    for age in range(4):
        hits = cf.step(loads(), queries((10, 2, True), None, None))
        assert hits[0] is True, f"age {age} must hit"
    # Dequeued after the fourth edge: the line now misses (expired).
    hits = cf.step(loads(), queries((10, 2, True), None, None))
    assert hits[0] is False
    # Way and index both participate in the match.
    cf.step(loads((33, 1)), queries())
    hits = cf.step(loads(), queries((33, 1, True), None, None))
    assert hits[0] is True
    for probe in ((33, 0), (34, 1), (33, 2), (32, 1)):
        hits = cf.step(loads(), queries((*probe, True), None, None))
        assert hits[0] is False, probe


# CF-FP-005
def test_duplicate_and_distinct_loads(cf):
    cf.reset()
    cf.step(loads((7, 0), (7, 0), (7, 0)), queries())
    hits = cf.step(loads(), queries((7, 0, True), (7, 0, True), (7, 0, True)))
    assert all(hits)
    cf.step(loads((8, 1), (9, 2), (10, 3)), queries())
    hits = cf.step(loads(), queries((8, 1, True), (9, 2, True), (10, 3, True)))
    assert all(hits)
    # Port 0 can be invalid while later ports still enqueue in order.
    cf.step(loads(None, (11, 0), (12, 1)), queries())
    hits = cf.step(loads(), queries((11, 0, True), (12, 1, True), None))
    assert hits[0] and hits[1]


# CF-FP-005, CF-FP-006
def test_capacity_full_and_pointer_wrap(cf):
    cf.reset()
    stored = []
    for cycle in range(5):
        three = [(cycle * 3 + port, port & 3) for port in range(3)]
        stored.extend(three)
        cf.step(loads(*three), queries())
    assert cf.model.occupancy == 12, cf.model.occupancy
    # The three oldest entries are already dequeued; the remaining 12 are
    # visible, three per cycle.
    for base in range(3, 15, 3):
        probes = tuple((*stored[base + port], True) for port in range(3))
        hits = cf.step(loads(), queries(*probes))
        assert all(hits), (base, hits)
    for base in range(0, 3):
        hits = cf.step(loads(), queries((*stored[base], True), None, None))
        assert hits[0] is False
    # Keep the same bandwidth: dequeue and enqueue balance at 12 in flight
    # while the enqueue pointer wraps at 15.
    for cycle in range(8):
        three = [(64 + cycle * 3 + port, (port + 1) & 3) for port in range(3)]
        cf.step(loads(*three), queries())
        assert cf.model.occupancy <= 12, (cycle, cf.model.occupancy)
    # Newest lines are visible right after their enqueue edge.
    newest = [(64 + 7 * 3 + port, (port + 1) & 3) for port in range(3)]
    hits = cf.step(loads(), queries(*(tuple((*entry, True)) for entry in newest)))
    assert all(hits)
    # Drain and confirm an empty FIFO.
    for _ in range(10):
        cf.step(loads(), queries())
    assert cf.model.occupancy == 0
    hits = cf.step(loads(), queries((*newest[0], True), None, None))
    assert hits[0] is False


# CF-FP-003, CF-FP-006
def test_query_ports_are_independent(cf):
    cf.reset()
    cf.step(loads((20, 0), (21, 1), (22, 2)), queries())
    # Three hits on three different lines in one cycle.
    hits = cf.step(loads(), queries((20, 0, True), (21, 1, True), (22, 2, True)))
    assert hits == [True, True, True]
    # Mixed hit / miss / invalid on the same cycle.
    hits = cf.step(loads(), queries((20, 0, True), (99, 3, True), (21, 1, False)))
    assert hits == [True, False, False]
    # Enqueue and query in the same cycle: the new entry is not visible yet.
    hits = cf.step(loads((23, 3)), queries((23, 3, True), None, None))
    assert hits[0] is False
    hits = cf.step(loads(), queries((23, 3, True), None, None))
    assert hits[0] is True


# CF-FP-002, CF-FP-003
def test_index_and_way_full_range(cf):
    cf.reset()
    entries = [(0, 0), (1, 1), (127, 2), (128, 3), (254, 0), (255, 1)]
    cf.step(loads(entries[0], entries[1], entries[2]), queries())
    cf.step(loads(entries[3], entries[4], entries[5]), queries())
    hits = cf.step(loads(), queries(*(tuple((*entry, True)) for entry in entries[:3])))
    assert all(hits)
    hits = cf.step(loads(), queries(*(tuple((*entry, True)) for entry in entries[3:])))
    assert all(hits)
    # Every way is also exercised by misses.
    for probe in ([(50, 0)], [(51, 1), (52, 2)], [(53, 3)]):
        hits = cf.step(loads(), queries(*(tuple((*entry, True)) for entry in probe)))
        assert all(hit is False for hit in hits), probe


# CF-FP-001..006
def test_random_legal_traffic(cf):
    rng = random.Random(0xC0FF_2026)
    cf.reset()
    for cycle in range(300):
        count = rng.choice((0, 1, 1, 2, 3))
        load_list = []
        for _ in range(count):
            if load_list and rng.random() < 0.2:
                load_list.append(load_list[0])
            else:
                load_list.append((rng.randrange(256), rng.randrange(4)))
        probes = []
        for _ in range(3):
            if rng.random() < 0.2:
                probes.append(None)
            elif rng.random() < 0.5 and load_list:
                probes.append((*rng.choice(load_list), True))
            else:
                probes.append((rng.randrange(256), rng.randrange(4),
                               rng.random() < 0.8))
        cf.step(loads(*load_list), queries(*probes), context=f"random {cycle}")
