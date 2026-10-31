"""ResolveQueue streaming wrap: all physical and branch slots stay usable."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import head

pytestmark = [pytest.mark.feature("FTQ-RQ-002"), pytest.mark.feature("FTQ-RQ-006")]


async def test_all_physical_and_branch_slots_survive_streaming_wrap(resolve_queue_agent):
    from tests.resolve_queue.support import report

    agent = resolve_queue_agent
    offset = 0
    for entry_index in range(32):
        for group in range(2):
            await agent.resolve_mixed(
                [report(entry_index, offset=offset + group * 4 + lane,
                        target=0x9000_0000 + (group * 4 + lane) * 0x100)
                 for lane in range(3)],
                ifu=report(entry_index, offset=offset + group * 4 + 3,
                           target=0x9000_0000 + (group * 4 + 3) * 0x100),
            )
        assert head(agent) == (entry_index, 0, 0x8000_1000)
        assert [branch.position for branch in agent.training().branches] == [
            offset + lane for lane in range(8)]
        await agent.drain()
        offset = (offset + 8) & 0x1F
    assert agent.training() is None
