"""CommitQueue mixed-lane streaming against the independent FIFO model."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ftq.oracle import CallRet

WIDTH = 8


@pytest.mark.feature("FTQ-CQ-002")
async def test_mixed_lane_stream_matches_independent_fifo_model(commit_queue_agent):
    agent = commit_queue_agent
    rng = random.Random(0xC0FFEE)
    ptr = 0
    for _ in range(240):
        values = []
        for _ in range(WIDTH):
            if rng.random() < 0.35:
                values.append(None)
                continue
            values.append(CallRet(ptr % 64, rng.randrange(4)))
            ptr += 1
        await agent.submit(tuple(values))
    for _ in range(80):
        if await agent.submit((None,) * WIDTH) is None:
            break
    assert agent.checker.depth == 0
