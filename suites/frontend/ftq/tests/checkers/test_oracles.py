"""Checker self-checks: the oracles must reject wrong answers."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.oracle import CallRetFifo
from suites.frontend.ftq.oracle import ResolveBranch
from suites.frontend.ftq.oracle import ResolveMergeModel


@pytest.mark.selftest
def test_callret_fifo_detects_reordered_and_corrupted_payloads():
    model = CallRetFifo()
    head = model.step((CallRet(1, 1), CallRet(2, 1)))
    assert head == CallRet(1, 1)
    assert head != CallRet(2, 1)
    assert head != CallRet(1, 2)
    assert model.step((None,) * 8) == CallRet(2, 1)
    assert model.step((None,) * 8) is None


@pytest.mark.selftest
def test_callret_fifo_guard_is_part_of_the_oracle():
    model = CallRetFifo()
    rows = tuple(CallRet(index, 1) for index in range(8))
    depth = lambda: (model.enq - model.deq) % model.capacity
    for _ in range(20):
        if depth() >= model.capacity - model.guard:
            break
        model.step(rows)
    else:
        raise AssertionError("the selective FIFO never reached its reserve")

    # While the reserve is active the whole group is rejected, so enqueue
    # does not advance; the head may still be consumed.
    while depth() >= model.capacity - model.guard:
        before = model.enq
        model.step(rows)
        assert model.enq == before
    before = model.enq
    model.step(rows)
    assert (model.enq - before) % model.capacity == 8


@pytest.mark.selftest
def test_merge_model_detects_lost_order_and_wrong_flush_scope():
    model = ResolveMergeModel()
    first = ResolveBranch(1, 0x1000, 1, 1, 1, 0, "b0")
    second = ResolveBranch(2, 0x2000, 1, 1, 1, 0, "b1")
    model.push(7, 0, 0x8000_0000, first)
    model.push(7, 0, 0x8000_0000, second)
    head = model.head()
    assert head is not None
    assert [branch.position for branch in head.branches] == [1, 2]
    assert [branch.position for branch in head.branches] != [2, 1]
    assert [branch.position for branch in head.branches] != [1]

    model.push(8, 0, 0x8000_0020, ResolveBranch(3, 0x3000, 1, 1, 1, 0, "b2"))
    model.redirect(7, 0)
    # The younger entry keeps its physical slot until it reaches the head;
    # only its training eligibility is withdrawn.
    assert model.mem[(model.deq + 1) % model.capacity].flushed
    assert model.head().index == 7
    model.pop()
    assert model.head() is None
    model.advance(1)
    assert model.head() is None

    model.push(7, 0, 0x8000_0000, first)
    model.bpu_enqueue(7)
    model.advance(1)
    assert model.head() is None


@pytest.mark.selftest
def test_merge_model_keeps_the_declared_eight_branch_capacity():
    model = ResolveMergeModel()
    for offset in range(1, 11):
        model.push(3, 0, 0x8000_0060,
                   ResolveBranch(offset, 0x9000_0000 + offset * 0x100,
                                 1, 1, 1, 0, "b0"))
    head = model.head()
    assert head is not None
    assert len(head.branches) == 8
    assert [branch.position for branch in head.branches] == list(range(1, 9))
    assert model.room(3) == 0
