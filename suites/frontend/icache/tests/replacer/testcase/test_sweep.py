"""Sweep every vSetIdx so all sets on both fetch ports are exercised.

A policy implementation that aliases sets, or that serves only the first set of
each port, passes any single-set test. This sweep touches and queries every
location and checks each answer against the reference model, which keeps
independent state per (port, set).
"""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-REPLACER-007")
async def test_every_vset_idx_touches_and_reports_a_victim(replacer_agent):
    agent = replacer_agent
    await agent.reset()

    # One request per location, then two requests in a single cycle per
    # location: the adapter has two candidate branches per fetch port, and the
    # second branch has its own state update path.
    for vset in range(agent.model.num_sets):
        way = vset % agent.model.num_ways
        await agent.apply_touches(vset, (way,))
    for vset in range(agent.model.num_sets):
        pair = (vset % agent.model.num_ways, (vset + 1) % agent.model.num_ways)
        await agent.apply_touches(vset, pair)

    # Every location must now disagree with a fresh policy in a way the model
    # predicts; probe them all.
    for vset in range(agent.model.num_sets):
        await agent.probe_victim(vset)


@pytest.mark.feature("ICACHE-REPLACER-007")
async def test_all_sets_share_the_same_policy_shape(replacer_agent):
    """Each location must respond to the same touch sequence identically."""
    agent = replacer_agent
    await agent.reset()
    sequence = (0, 1, 2, 3)
    answers = {}
    for vset in range(0, agent.model.num_sets, 3):
        await agent.apply_touches(vset, sequence)
    for vset in range(0, agent.model.num_sets, 3):
        answers[vset] = await agent.request_victim(vset)
    assert len(set(answers.values())) == 1, (
        f"locations with the same history disagree: {sorted(set(answers.values()))}")


@pytest.mark.feature("ICACHE-REPLACER-004")
async def test_victim_feedback_and_explicit_touch_may_share_a_cycle(replacer_agent):
    """A refill request and a new lookup touch can target the same set.

    Both must be applied (the adapter latches the victim for the next edge while
    the explicit touch is applied now); the model replays exactly that order.
    """
    agent = replacer_agent
    await agent.reset()
    for vset in range(agent.model.num_sets):
        way = (vset + 2) % agent.model.num_ways
        if vset % 2 == 0:
            await agent.touch_cycle(port0=((vset, way),), victim_vset=vset)
        else:
            await agent.touch_cycle(port1=((vset, way),), victim_vset=vset)
    for vset in range(agent.model.num_sets):
        await agent.probe_victim(vset)
