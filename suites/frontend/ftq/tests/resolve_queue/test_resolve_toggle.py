"""ResolveQueue payload breadth: all branch bits one then zero per slot."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-002")

ONES_TARGET = (1 << 49) - 1


async def _fill(agent, index: int, *, ones: bool) -> None:
    for group in range(2):
        reports = [report(
            index,
            offset=31 if ones else 0,
            target=ONES_TARGET if ones else 0,
            taken=1 if ones else 0,
            mispredict=1 if ones else 0,
            branch_type=3 if ones else 0,
            ras_action=3 if ones else 0,
        ) for _ in range(3)]
        await agent.resolve(reports)
        await agent.resolve([report(
            index,
            offset=31 if ones else 0,
            target=ONES_TARGET if ones else 0,
            taken=1 if ones else 0,
            mispredict=1 if ones else 0,
            branch_type=3 if ones else 0,
            ras_action=3 if ones else 0,
        )], source="ifu")
    await agent.drain()


async def test_all_branch_payload_bits_toggle_in_every_physical_slot(resolve_queue_agent):
    agent = resolve_queue_agent
    for index in range(16):
        await _fill(agent, index, ones=True)
    for index in range(16):
        await _fill(agent, index, ones=False)
    assert agent.training() is None
