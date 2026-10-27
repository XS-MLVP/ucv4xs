from __future__ import annotations

import pytest

@pytest.mark.feature("ICACHE-MSHR-005")
async def test_a_new_miss_is_accepted_after_fencei(mshr_agent):
    """fence.i must release the entry, not leave a sticky drop flag."""
    agent = mshr_agent
    first, first_set = 0x12340, 0x21
    await agent.allocate(first, first_set)
    await agent.issue(1)
    await agent.flush()
    # The issued transaction drains before the entry is reusable; the miss
    # unit completes it with the invalid handshake.
    await agent.complete()

    second, second_set = 0x23450, 0x22
    await agent.allocate(second, second_set)
    await agent.issue(2)
    await agent.complete()
    assert agent.model.state.valid == 0
    assert agent.req_ready() == 1
