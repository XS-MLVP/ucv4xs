"""RAS push, LIFO and repeated-address behavior."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ras.checker.assertions import expected_top
from suites.frontend.bpu.ras.checker.assertions import pop
from suites.frontend.bpu.ras.checker.assertions import push
from suites.frontend.bpu.ras.case.definitions import CALL_A
from suites.frontend.bpu.ras.case.definitions import CALL_B
from suites.frontend.bpu.ras.case.definitions import unique_calls
from suites.frontend.bpu.ras.transaction.types import RasOperation


@pytest.mark.feature("BPU-RAS-002")
async def test_call_push_computes_return_address(ras_agent):
    await ras_agent.reset()
    assert (await push(ras_agent, CALL_A)).top == expected_top(CALL_A)


@pytest.mark.feature("BPU-RAS-002")
async def test_neutral_beat_after_call_keeps_the_just_pushed_return_address(ras_agent):
    """A call's return address stays visible through the next neutral beat.

    The pushed entry is written at the end of the call beat; the immediately
    following adjacent beat that neither pushes nor pops must still expose that
    entry, and the following return must consume it. This is the observable
    lifetime of one real call, not a second encoding of the same push.
    """

    await ras_agent.reset()
    call = RasOperation(2, start_pc=CALL_A.start_pc, position=CALL_A.position)
    adjacent = await ras_agent.act_many((call, RasOperation(0)))
    assert adjacent[0].top == expected_top(CALL_A)
    assert adjacent[1].top == adjacent[0].top
    assert adjacent[1].redirect_meta["sctr"] == adjacent[0].redirect_meta["sctr"]
    consumed = await pop(ras_agent)
    assert consumed.top != adjacent[0].top


@pytest.mark.feature("BPU-RAS-003")
async def test_return_pop_is_lifo(ras_agent):
    await ras_agent.reset()
    await push(ras_agent, CALL_A)
    await push(ras_agent, CALL_B)
    assert (await pop(ras_agent)).top == expected_top(CALL_A)


@pytest.mark.feature("BPU-RAS-003")
async def test_deep_nesting_crosses_pointer_wrap_and_unwinds_in_lifo_order(ras_agent):
    """Twelve distinct calls exceed the eight-entry committed-stack pointer.

    The committed stack metadata pointer is three bits wide in the rebuilt
    MinimalConfig. Nesting past its eight-entry wrap must still keep every
    speculative frame distinct: the unwound tops are the exact return
    addresses in reverse order, not aliases of the first eight calls.
    """

    calls = unique_calls()[:12]
    await ras_agent.reset()
    initial = ras_agent.snapshot()
    for call in calls:
        assert (await push(ras_agent, call)).top == expected_top(call)
    # Each pop removes the current youngest frame and exposes the next one, so
    # the first pop after twelve calls exposes call 10, and the twelfth
    # removes call 0 and returns the initial empty-stack top.
    for call in reversed(calls[:-1]):
        assert (await pop(ras_agent)).top == expected_top(call)
    assert (await pop(ras_agent)).top == initial.top


@pytest.mark.feature("BPU-RAS-004")
async def test_repeated_address_counter_preserves_top_until_last_pop(ras_agent):
    await ras_agent.reset()
    initial = ras_agent.snapshot()
    for _ in range(3):
        await push(ras_agent, CALL_A)

    assert (await pop(ras_agent)).top == expected_top(CALL_A)
    assert (await pop(ras_agent)).top == expected_top(CALL_A)
    assert (await pop(ras_agent)).top == initial.top
