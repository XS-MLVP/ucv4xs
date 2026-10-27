"""Teach every set every touch order and check the policy state.

TREE-PLRU stores three bits per set.  A test that only touches ways 0/1 leaves
large parts of that state graph unvisited: the victim after a given history is
what exposes a wrong tree update, so each of the 24 way orders is applied from
reset and the next victim is checked against the reference policy.
"""

from __future__ import annotations

import itertools

import pytest


@pytest.mark.feature("ICACHE-REPLACER-001")
async def test_every_touch_order_drives_the_policy_state(replacer_agent):
    agent = replacer_agent
    for order in itertools.permutations(range(agent.model.num_ways)):
        await agent.reset()
        for vset in range(agent.model.num_sets):
            await agent.apply_touches(vset, order)
            await agent.probe_victim(vset)
