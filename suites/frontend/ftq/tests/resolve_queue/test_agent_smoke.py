"""Agent smoke: the driver/monitor/checker path reaches the training port."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import head
from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-001")


async def test_agent_round_trip(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5, offset=3)])
    assert head(agent) == (5, 0, 0x8000_1000)
    assert len(agent.training().branches) == 1
