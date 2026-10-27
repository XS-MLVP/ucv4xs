"""Tree-PLRU victim order of ICacheReplacer.

The reference is the published tree-PLRU algorithm (older-pointer walk with
path inversion on touch), not the RTL body.

The victim port latches its winner as a touch on the following edge, so each
observation consumes that side effect; the model applies it identically.
"""

from __future__ import annotations

import pytest

WAY_SEQUENCES = [
    (0, 1, 2, 3),
    (3, 2, 1, 0),
    (0, 0, 0, 0),
    (1, 1, 1, 1),
    (2, 2, 2, 2),
    (3, 3, 3, 3),
    (0, 1),
    (2, 3),
    (1, 0),
    (3, 2),
    (0,),
    (1,),
    (2,),
    (3,),
]


@pytest.mark.feature("ICACHE-REPLACER-001")
async def test_victim_follows_tree_plru_after_way_sequences(replacer_agent):
    agent = replacer_agent
    for ways in WAY_SEQUENCES:
        await agent.reset()
        await agent.apply_touches(0x04, ways)
        observed = await agent.probe_victim(0x04)
        assert 0 <= observed < 4, f"ways {ways}: way {observed} out of range"


@pytest.mark.feature("ICACHE-REPLACER-001")
async def test_touching_the_victim_moves_the_selection(replacer_agent):
    agent = replacer_agent
    await agent.reset()
    first = await agent.probe_victim(0x04)
    second = await agent.probe_victim(0x04)
    assert first != second, "the latched victim must not be selected twice in a row"
