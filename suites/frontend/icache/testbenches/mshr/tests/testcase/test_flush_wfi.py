"""Flush, fence.i and WFI interaction of the MSHR.

Dropping the entry too early loses an outstanding memory transaction, so the
contract distinguishes "not issued" from "issued".
"""

from __future__ import annotations

import pytest

BLOCK = 0x2000
VSET = 0x04


@pytest.mark.feature("ICACHE-MSHR-005")
async def test_fencei_before_issue_drops_the_entry(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    await agent.flush()
    assert agent.info_valid() == 0, "an unissued request is dropped immediately"
    assert await agent.check_hits((BLOCK, VSET)) == (0, 0), "a dropped entry is not a hit"
    assert agent.wfi_safe() == 1, "nothing is outstanding"
    await agent.wait_for(lambda: agent.req_ready() == 1, what="entry release after fence.i")


@pytest.mark.feature("ICACHE-MSHR-006")
async def test_fencei_after_issue_drains_without_publishing(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    await agent.issue(victim_way=0b01)
    await agent.flush()
    assert agent.info_valid() == 0, "a draining entry must not publish bypass data"
    assert await agent.check_hits((BLOCK, VSET)) == (0, 0), "a draining entry is not a hit"
    assert agent.wfi_safe() == 0, "the outstanding transaction still blocks WFI"
    assert agent.req_ready() == 0, "a new request must wait until the drain finishes"
    await agent.complete()
    await agent.wait_for(lambda: agent.req_ready() == 1, what="entry release after drain")
    assert agent.wfi_safe() == 1


@pytest.mark.feature("ICACHE-MSHR-007")
async def test_wfi_safe_tracks_outstanding_requests(mshr_agent):
    agent = mshr_agent
    assert agent.wfi_safe() == 1, "an empty MSHR is WFI safe"
    await agent.allocate(BLOCK, VSET)
    assert agent.wfi_safe() == 1, "an unissued request cannot block WFI"
    await agent.issue(victim_way=0b00)
    assert agent.wfi_safe() == 0, "an issued request blocks WFI"


@pytest.mark.feature("ICACHE-MSHR-007")
async def test_wfi_request_holds_the_acquire(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    # A pending WFI request must keep the acquire from being issued.
    agent.set_wfi(1)
    agent.set_acquire_ready(1)
    for _ in range(4):
        await agent.tick()
        assert agent.acquire_valid() == 0, "a pending WFI request must hold the acquire"
    # An entry that never issued must keep the published WFI contract safe.
    assert agent.wfi_safe() == 1, "no memory transaction may be outstanding"
    agent.set_wfi(0)
    agent.set_acquire_ready(0)
    await agent.issue(victim_way=0b01)
    assert agent.wfi_safe() == 0, "the accepted acquire is now outstanding"


@pytest.mark.feature("ICACHE-MSHR-006")
async def test_fencei_in_the_completion_cycle_frees_the_entry_and_stays_usable(mshr_agent):
    """A refill completing while fence.i is asserted frees the entry at once.

    Completion wins over the flush: the transaction is over rather than
    aborted, so the entry is released instead of draining and the miss unit does
    not stall waiting for a response that will never come.  The flush state left
    behind by the collision must not mute the MSHR forever, so a following
    allocation must publish its bypass information again.
    """
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    await agent.issue(victim_way=0b10)

    # Both controls are driven before the same edge.  ``req.ready`` is gated
    # by ``fence.i`` itself, so the entry release is only observable once the
    # flush level drops: ready rising proves the entry was freed rather than
    # merely muted.
    await agent.complete_while_flushing()

    assert agent.info_valid() == 0, "the completed entry must stop publishing"
    assert agent.wfi_safe() == 1, "the completed transaction must not stay outstanding"

    # The internal flush state must be cleared by the next allocation; if it
    # stayed sticky, info.valid would never rise again and allocate() would
    # time out here.
    await agent.allocate(BLOCK + 0x40, (VSET + 1) & 0xFF)
    assert agent.info_valid() == 1, (
        "the MSHR must publish bypass information again after a fence.i collision")
    await agent.issue(victim_way=0b01)
    await agent.complete()
    assert agent.info_valid() == 0 and agent.req_ready() == 1
