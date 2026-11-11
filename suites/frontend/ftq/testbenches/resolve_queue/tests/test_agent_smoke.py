"""Agent smoke: the driver/monitor/checker path reaches the training port."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.testbenches.resolve_queue.tests.support import head
from suites.frontend.ftq.testbenches.resolve_queue.tests.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-001")


async def test_agent_round_trip(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5, offset=3)])
    assert head(agent) == (5, 0, 0x8000_1000)
    assert len(agent.training().branches) == 1
    await agent.drain_all()
