"""Architectural scenarios only: no raw pins, edge waits, tasks or DUT lifetime."""
import pytest

from suites.vector.vagq.manager.types import Allocation, Beat, Offer
from suites.vector.vagq.manager.model import positions
from suites.vector.vagq.manager.cases import EFFECT_CASES, all_ring_offers, priority_and_wrap, random_controls


async def test_single_request_is_observed_on_its_launch_not_one_edge_late(manager_env):
    agent = manager_env.agent
    await agent.reset()
    first = await agent.offer(1)
    second = await agent.offer(1)
    assert first == Allocation(1, 0, 0x01)
    assert second == Allocation(1, 1, 0x02)
    await agent.stream([Beat()])
    assert manager_env.checker.checked_cycles > 0
    assert manager_env.checker.board.status.failed == 0


async def test_all_occupancies_request_validity_and_count_encodings(manager_env):
    agent = manager_env.agent
    await agent.reset()
    before = agent.launch_board.status.checked
    await agent.stream(all_ring_offers())
    assert agent.launch_board.status.checked - before == 256 * 2 * 16 * 2 + 1
    assert manager_env.checker.board.status.failed == 0


async def test_priority_effects_wrap_release_and_reset_are_checked(manager_env):
    agent = manager_env.agent
    await agent.reset()
    await agent.stream(priority_and_wrap())
    for group in manager_env.coverage.groups.values():
        group.assert_coverage(100)
    # Reset while occupied, then prove the first allocation is back at zero.
    await agent.reset()
    assert await agent.offer(8) == Allocation(1, 0, 255)
    await agent.stream([Beat()])


async def test_contiguous_control_sequences_have_no_model_resynchronization(manager_env):
    agent = manager_env.agent
    await agent.reset()
    for seed in (1, 0x4566D5, 0xA55A):
        await agent.stream(random_controls(seed, 512))
    assert manager_env.checker.board.status.checked > 1536 * 2
    assert manager_env.checker.board.status.failed == 0


@pytest.mark.parametrize('name,initial,target,free', EFFECT_CASES, ids=[row[0] for row in EFFECT_CASES])
async def test_priority_transition_has_complete_later_allocation_consumers(
    manager_env, name, initial, target, free
):
    agent = manager_env.agent
    await agent.reset()
    await agent.recover(positions(initial))
    await agent.apply(target)
    for position in free:
        result = await agent.offer(1)
        assert result == Allocation(1, position, 1 << position), name
    # Each successful request is consumed before the next is offered. An
    # extra free bit must not hide beyond the last expected position.
    assert await agent.offer(1) == Allocation(), name
    await agent.stream([Beat()])
