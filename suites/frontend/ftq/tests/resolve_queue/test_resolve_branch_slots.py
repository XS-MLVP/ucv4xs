"""ResolveQueue: all eight branch slots fill in source order."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import positions
from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-002")


async def test_one_entry_accepts_all_eight_branch_slots_in_source_order(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve_mixed(
        [report(6, pc=0x8000_6000, offset=1, target=0x8000_6100),
         report(6, pc=0x8000_6000, offset=2, target=0x8000_6200),
         report(6, pc=0x8000_6000, offset=3, target=0x8000_6300)],
        ifu=report(6, pc=0x8000_6000, offset=4, target=0x8000_6400),
    )
    await agent.resolve_mixed(
        [report(6, pc=0x8000_6000, offset=5, target=0x8000_6500),
         report(6, pc=0x8000_6000, offset=6, target=0x8000_6600),
         report(6, pc=0x8000_6000, offset=7, target=0x8000_6700)],
        ifu=report(6, pc=0x8000_6000, offset=8, target=0x8000_6800),
    )

    training = agent.training()
    assert training is not None
    assert (training.index, training.flag) == (6, 0)
    assert positions(agent) == list(range(1, 9))
    assert [branch.target for branch in training.branches] == [
        0x8000_6100 + slot * 0x100 for slot in range(8)]
    await agent.drain()
    await agent.step(2)
    assert agent.training() is None
