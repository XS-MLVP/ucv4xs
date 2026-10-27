"""Independent small-state oracle and priority qualification, not DUT evidence."""
from itertools import product

import pytest

from vagqverify.manager.model import State, positions
from vagqverify.manager.types import Allocation, Beat, Idle, Offer

pytestmark = pytest.mark.toffee_functional_coverage(False)


def integer_oracle(bitmap, valid, count):
    if valid and 1 <= count <= 8:
        for start in range(8):
            unrolled = ((1 << count) - 1) << start
            mask = (unrolled | (unrolled >> 8)) & 255
            if bitmap & mask == 0:
                return Allocation(1, start, mask)
    return Allocation()


def test_all_ring_decisions_against_separate_integer_oracle():
    for bitmap, valid, count in product(range(256), (0, 1), range(16)):
        tx = Beat(Offer(count) if valid else Idle(count))
        assert State(positions(bitmap)).decision(tx) == integer_oracle(bitmap, valid, count)


@pytest.mark.parametrize('bitmap', [0, 0x55, 0xFF])
@pytest.mark.parametrize('redirect,walk,reset', tuple(product((0, 1), repeat=3)))
def test_update_priorities(bitmap, redirect, walk, reset):
    state = State(positions(bitmap))
    tx = Beat(Offer(2), released=positions(0x8F),
              recovery=positions(0xA5) if redirect else None,
              walked=positions(0x81) if walk else None)
    decision = integer_oracle(bitmap, 1, 2)
    expected = (bitmap & ~0x8F) | (0x81 if walk else decision.mask)
    if redirect:
        expected = 0xA5
    if reset:
        expected = 0
    assert state.following(tx, reset=bool(reset)) == State(positions(expected))


def test_same_edge_release_cannot_supply_a_candidate():
    full = State(positions(255))
    tx = Beat(Offer(2), released=frozenset({0, 1}))
    assert full.decision(tx) == Allocation()
    assert full.following(tx) == State(positions(252))
    assert full.following(tx).decision(Beat(Offer(2))) == Allocation(1, 0, 3)


@pytest.mark.parametrize('factory', [lambda: Offer(16), lambda: Idle(-1),
                                    lambda: Beat(released=frozenset({8}))])
def test_invalid_transaction_fields_fail_instead_of_truncating(factory):
    with pytest.raises(ValueError):
        factory()
