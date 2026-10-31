"""ResolveQueue: circular-pointer flag is part of FTQ entry identity."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import head
from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-001")


async def test_same_index_with_different_pointer_flag_has_separate_identity(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(0, flag=1, offset=1)])
    assert head(agent) == (0, 1, 0x8000_1000)
    await agent.resolve([report(0, flag=0, offset=2)])
    assert head(agent) == (0, 1, 0x8000_1000)

    await agent.drain()
    assert head(agent) == (0, 0, 0x8000_1000)
    await agent.drain()
    await agent.step(2)
    assert agent.training() is None
