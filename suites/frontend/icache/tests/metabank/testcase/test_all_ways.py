"""Every set and every way marks and clears its own valid bit.

The validity array is indexed by (set, way); a refill of way 3 in set 0x7F must
not touch way 3 in any other set, and ``flushAll`` must clear every one of the
512 bits.  A single-way sweep would miss the per-way decode entirely.
"""

from __future__ import annotations

import pytest

from icacheverify.metabank.model.bank import MetaEntry
from icacheverify.metabank.model.bank import MetaWay


@pytest.mark.feature("ICACHE-METABANK-009")
async def test_every_way_of_every_set_is_set_and_cleared(metabank_agent):
    agent = metabank_agent
    for set_index in range(agent.model.sets):
        for way in range(agent.model.ways):
            await agent.write(set_index, 1 << way,
                              phy_tag=0x4000 + set_index,
                              code=(set_index ^ way) & 1)
    for set_index in range(agent.model.sets):
        entries = await agent.check_read(set_index)
        assert [entry.valid for entry in entries] == [1, 1, 1, 1], (
            f"set {set_index} did not mark every written way valid")
        for way, entry in enumerate(entries):
            assert entry.entry == MetaEntry(0x4000 + set_index, 0,
                                             (set_index ^ way) & 1), (
                f"set {set_index} way {way} lost its entry")

    await agent.flush_all()
    for set_index in range(agent.model.sets):
        entries = await agent.check_read(set_index)
        assert [entry.valid for entry in entries] == [0, 0, 0, 0], (
            f"set {set_index} kept a valid way after flushAll")
