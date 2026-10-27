"""Set, port and feedback isolation of ICacheReplacer.

Policy state is per (port, set). A test that only ever exercises one location
can pass with a single shared state register, so each case touches one location
and then checks every other location against the reference model.
"""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-REPLACER-002")
async def test_touching_one_set_does_not_disturb_other_sets(replacer_agent):
    agent = replacer_agent
    await agent.reset()
    await agent.apply_touches(0x10, (0, 1, 2, 3))
    for vset in (0x00, 0x02, 0x04, 0x20, 0x30):
        if vset == 0x10:
            continue
        # probe_victim compares against the model, which only touched 0x10.
        await agent.probe_victim(vset)


@pytest.mark.feature("ICACHE-REPLACER-003")
async def test_fetch_ports_keep_independent_policy_state(replacer_agent):
    """The low vSetIdx bit selects the replacer; the rest is the set index."""
    agent = replacer_agent
    await agent.reset()
    assert agent.model.port_of(0x10) == 0 and agent.model.set_of(0x10) == 8
    assert agent.model.port_of(0x11) == 1 and agent.model.set_of(0x11) == 8

    # Same set index on the other port must keep its own history.
    await agent.apply_touches(0x10, (0, 1, 2, 3))
    await agent.probe_victim(0x11)


@pytest.mark.feature("ICACHE-REPLACER-004")
async def test_victim_feedback_advances_the_policy(replacer_agent):
    """Requesting a victim without an explicit touch still moves the policy."""
    agent = replacer_agent
    await agent.reset()
    seen = [await agent.probe_victim(0x12) for _ in range(6)]
    assert seen[0] != seen[1], "the latched victim must be replayed as a touch"
    assert len(set(seen)) >= 3, f"feedback stalled: sequence {seen}"


@pytest.mark.feature("ICACHE-REPLACER-005")
async def test_two_touches_on_one_port_are_applied_in_order(replacer_agent):
    agent = replacer_agent
    await agent.reset()
    # ``probe_victim`` already compares the observation with the model, whose
    # two touches are applied in request order.
    await agent.touch_cycle(port0=((0x14, 0), (0x14, 1)))
    await agent.probe_victim(0x14)

    await agent.reset()
    await agent.touch_cycle(port0=((0x14, 2), (0x14, 3)))
    await agent.probe_victim(0x14)

    # Two requests in one cycle must equal two requests in separate cycles in
    # the same order: batching must not reorder or drop a candidate way.
    await agent.reset()
    await agent.touch_cycle(port0=((0x14, 0), (0x14, 1)))
    batched = await agent.request_victim(0x14)
    await agent.reset()
    await agent.apply_touches(0x14, (0,))
    await agent.apply_touches(0x14, (1,))
    sequential = await agent.request_victim(0x14)
    assert batched == sequential, "one-cycle order differs from sequential order"


@pytest.mark.feature("ICACHE-REPLACER-006")
async def test_idle_cycles_do_not_advance_the_policy(replacer_agent):
    agent = replacer_agent
    await agent.reset()
    await agent.apply_touches(0x16, (0, 1))
    for _ in range(4):
        await agent.idle_cycle()
    await agent.probe_victim(0x16)


@pytest.mark.feature("ICACHE-REPLACER-003")
async def test_both_fetch_ports_touch_in_the_same_cycle(replacer_agent):
    """Both fetch ports update their policy state on the same edge.

    The replacer is shared by two fetch ports; the array is indexed by the set
    and the port selects which half of the entry is updated.  A design that
    served only one port per cycle, or that aliased the two ports' updates,
    would still pass any single-port test.
    """
    agent = replacer_agent
    await agent.reset()
    # Port 0 owns even set indices, port 1 odd ones.
    for index in range(8):
        even, odd = 2 * index, 2 * index + 1
        await agent.touch_cycle(port0=((even, index % 4),),
                                port1=((odd, (index + 1) % 4),))
    for index in range(8):
        await agent.probe_victim(2 * index)
        await agent.probe_victim(2 * index + 1)


@pytest.mark.feature("ICACHE-REPLACER-003")
async def test_both_ports_can_drive_two_requests_each_in_one_cycle(replacer_agent):
    """Four touches (two per port) land on the same edge."""
    agent = replacer_agent
    await agent.reset()
    for index in range(8):
        even, odd = 2 * index, 2 * index + 1
        await agent.touch_cycle(
            port0=((even, 0), (even, 1)),
            port1=((odd, 2), (odd, 3)))
    for index in range(8):
        await agent.probe_victim(2 * index)
        await agent.probe_victim(2 * index + 1)


@pytest.mark.feature("ICACHE-REPLACER-004")
async def test_victim_request_with_both_ports_active(replacer_agent):
    """A victim request shares the edge with touches on both ports.

    The victim port latches its answer and replays it as a touch on the next
    edge, so it must compose with the explicit touches of the same edge without
    losing either update.
    """
    agent = replacer_agent
    await agent.reset()
    for index in range(8):
        even, odd = 2 * index, 2 * index + 1
        await agent.touch_cycle(
            port0=((even, 1), (even, 2)),
            port1=((odd, 3), (odd, 0)),
            victim_vset=even)
    for index in range(8):
        await agent.probe_victim(2 * index)
        await agent.probe_victim(2 * index + 1)
