"""ResolveQueue: every backend/IFU lane-validity combination has one owner."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import head
from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-002")


async def test_every_backend_ifu_lane_validity_combination_has_one_owner(resolve_queue_agent):
    agent = resolve_queue_agent
    for combo in range(16):
        expected = [lane for lane in range(3) if combo & (1 << lane)]
        ifu = (combo & 8) != 0
        if not expected and not ifu:
            await agent.step(2)
            assert agent.training() is None
            continue
        reports = [report(combo, offset=lane + 1,
                          target=0x9000_0000 + lane * 0x100)
                   for lane in expected]
        await agent.resolve_mixed(
            reports,
            ifu=report(combo, offset=4, target=0x9000_0400) if ifu else None,
        )
        first_position = min([lane + 1 for lane in expected] +
                             ([4] if ifu else []))
        assert head(agent) == (combo, 0, 0x8000_1000)
        training = agent.training()
        assert [branch.position for branch in training.branches] == (
            [lane + 1 for lane in expected] + ([4] if ifu else []))
        assert training.branches[0].position == first_position
        await agent.drain()


@pytest.mark.feature("FTQ-RQ-003")
async def test_same_index_partial_lane_groups_merge_without_duplicate(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(11, offset=2, target=0x9100_0200)])
    assert head(agent) == (11, 0, 0x8000_1000)
    await agent.resolve_mixed(
        [report(11, offset=3, target=0x9100_0300)],
        ifu=report(11, offset=4, target=0x9100_0400),
    )
    training = agent.training()
    assert training.index == 11
    assert [branch.position for branch in training.branches] == [2, 3, 4]
    assert training.start_pc == 0x8000_1000
    await agent.drain()
    await agent.step(2)
    assert agent.training() is None


@pytest.mark.feature("FTQ-RQ-002")
@pytest.mark.parametrize("lane", range(3))
async def test_backend_lane_and_ifu_same_index_merge_in_one_cycle(resolve_queue_agent, lane):
    agent = resolve_queue_agent
    lanes = [None, None, None]
    lanes[lane] = report(30 + lane, offset=lane + 1,
                         target=0x9500_0000 + lane * 0x100)
    await agent.resolve_mixed(
        lanes, ifu=report(30 + lane, offset=4, target=0x9500_0400))
    training = agent.training()
    assert training is not None
    assert training.index == 30 + lane
    assert [branch.position for branch in training.branches] == [lane + 1, 4]
    assert [branch.target for branch in training.branches] == [
        0x9500_0000 + lane * 0x100, 0x9500_0400]
    await agent.drain()
