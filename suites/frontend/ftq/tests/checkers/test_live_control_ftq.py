"""Live-observation control: a wrong expected value must fail the check."""

from __future__ import annotations

import pytest

from tests.ftq.support import allocate

pytestmark = pytest.mark.selftest


async def test_ftq_observations_are_live_and_comparable(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 1, base=0x8000_1000, with_meta=False)
    assert agent.entry(0).start_pc == 0x8000_1000
    assert agent.pointers().bpu.value == 1

    # Controlled negative controls: the same observation path must reject a
    # wrong PC and a wrong pointer.  This is a checker self-check, not extra
    # hardware credit.
    with pytest.raises(AssertionError):
        assert agent.entry(0).start_pc == 0x8000_1004
    with pytest.raises(AssertionError):
        assert agent.pointers().bpu.value == 2
