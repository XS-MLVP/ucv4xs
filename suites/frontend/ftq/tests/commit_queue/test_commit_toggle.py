"""CommitQueue payload breadth: all ones then all zeros in every slot."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.oracle import CallRet

WIDTH = 8


@pytest.mark.feature("FTQ-CQ-002")
async def test_call_return_pointer_bits_toggle_in_every_queue_slot(commit_queue_agent):
    agent = commit_queue_agent
    for value in (0x3F, 0x00):
        for _ in range(64):
            row = [None] * WIDTH
            row[0] = CallRet(value, 3)
            await agent.submit(tuple(row))
    for _ in range(2):
        await agent.submit((None,) * WIDTH)
    assert agent.training() is None
