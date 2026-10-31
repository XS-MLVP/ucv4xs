"""Live-observation control for the CommitQueue output payload."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.oracle import CallRet

pytestmark = pytest.mark.selftest


async def test_commit_observations_are_live_and_comparable(commit_queue_agent):
    agent = commit_queue_agent
    row = [None] * 8
    row[0] = CallRet(9, 2)
    await agent.drive(tuple(row))
    await agent.step(1)
    assert agent.training() == CallRet(9, 2)
    with pytest.raises(AssertionError):
        assert agent.training() == CallRet(9, 1)
    with pytest.raises(AssertionError):
        assert agent.training() == CallRet(10, 2)
