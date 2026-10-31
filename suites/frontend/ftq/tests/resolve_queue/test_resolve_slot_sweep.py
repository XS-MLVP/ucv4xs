"""ResolveQueue: branch slot × source priority sweep over all physical slots."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-002")


async def test_every_branch_slot_accepts_every_source_priority(resolve_queue_agent):
    agent = resolve_queue_agent
    for vector in range(16 * 8 * 4):
        branch_slot = (vector // 16) % 8
        source = (vector // 128) % 4
        index = (vector * 7) & 0x3F
        for fill in range(branch_slot):
            await agent.resolve([report(
                index, offset=fill, target=0x9300_0000 + fill * 0x100)])
        target = 0xA500_0000 + branch_slot * 0x100
        if source < 3:
            await agent.backend_lanes([
                report(index, offset=branch_slot, target=target)
                if lane == source else None
                for lane in range(3)
            ])
        else:
            await agent.resolve([report(index, offset=branch_slot,
                                        target=target)], source="ifu")
        training = agent.training()
        assert training is not None, (vector, branch_slot, source)
        assert training.index == index
        assert [branch.position for branch in training.branches] == list(
            range(branch_slot + 1))
        assert training.branches[branch_slot].target == (
            0xA500_0000 + branch_slot * 0x100)
        await agent.drain()
        await agent.step(1)
        assert agent.training() is None
