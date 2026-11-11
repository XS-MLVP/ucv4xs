"""Top-level IFU/backend same-index merge on the a0c2a26cb baseline.

The IFU resolve is registered from ``ifuRedirectReceiver`` while backend
reports are live.  A backend report for the same FTQ entry can therefore
arrive in the cycle after the IFU redirect is accepted, creating the entry
together with the registered IFU resolve.  This is a legal producer sequence
and exercises the three ``hitPrevious(3)`` mux arms that the 2026-10-30
coverage note incorrectly classified as structurally unreachable.
"""

from __future__ import annotations

import pytest

from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.ftq.tests.support import resolve

pytestmark = pytest.mark.feature("FTQ-TOP-015")


async def test_four_sources_can_merge_into_one_new_entry_in_one_cycle(ftq_agent):
    """The top-level producer width is three backend lanes plus one IFU."""

    agent = ftq_agent
    pc = 0x8000_0000
    await agent.predict(Prediction(pc, end_position=3))
    await agent.write_meta(Meta(0))

    ifu = IfuRedirect(0, pc=2 * pc, offset=4, target=2 * 0x8000_9000,
                      branch_type=1, ras_action=0, can_train=1)
    await agent.cycle(FtqInput(ifu_redirect=ifu))
    lanes = tuple(resolve(0, pc=pc, offset=offset, mispredict=0)
                  for offset in (1, 2, 3))
    await agent.cycle(FtqInput(resolve=lanes))
    await agent.resolve_release()
    await agent.consumers(train=1)
    for _ in range(8):
        training = agent.training()
        if training is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    assert [branch.position for branch in training.branches] == [1, 2, 3, 4]
    await agent.drain_training()


@pytest.mark.parametrize("lane", (0, 1, 2))
async def test_ifu_and_backend_resolve_create_the_same_new_entry_in_one_cycle(
        ftq_agent, lane):
    agent = ftq_agent
    pc = 0x8000_0000
    await agent.predict(Prediction(pc, end_position=3))
    await agent.write_meta(Meta(0))

    ifu = IfuRedirect(0, pc=2 * pc, offset=2, target=2 * 0x8000_9000,
                      branch_type=1, ras_action=0, can_train=1)
    # Edge 1: the IFU redirect is accepted and registers its resolve.
    await agent.cycle(FtqInput(ifu_redirect=ifu))
    # Edge 2: the registered IFU resolve and a live backend report have the
    # same ftqIdx, and no ResolveQueue entry exists yet, so both create the
    # entry and the IFU branch must reuse the backend lane's enqueue index.
    lanes = [None, None, None]
    lanes[lane] = resolve(0, pc=pc, offset=1, mispredict=0)
    await agent.cycle(FtqInput(resolve=tuple(lanes)))
    await agent.resolve_release()
    await agent.consumers(train=1)
    for _ in range(8):
        training = agent.training()
        if training is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    positions = [branch.position for branch in training.branches]
    assert positions == [1, 2], positions
    await agent.drain_training()
