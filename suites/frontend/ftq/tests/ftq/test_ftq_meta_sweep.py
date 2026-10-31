"""FTQ top: write the complete 64-entry metadata state space legally."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.ftq.transaction.types import PredictionSpec

pytestmark = pytest.mark.feature("FTQ-TOP-017")


async def test_metadata_queues_accept_every_physical_index(ftq_agent):
    agent = ftq_agent
    specs = [
        PredictionSpec(
            start_pc=0x8000_0000 + index * 0x20,
            meta=dict(
                redirectMeta_phr_phrPtr_value=index,
                redirectMeta_commonHRMeta_ghr=0x1000 + index,
                resolveMeta_phr_phrPtr_value=0x200 + index,
                commitMeta_ras_ssp=index & 0xF,
            ),
        )
        for index in range(64)
    ]
    await agent.allocate(specs, consume=True)
    for index in range(64):
        assert agent.meta_redirect(index, "phr_phrPtr_value") == index
        assert agent.meta_redirect(index, "commonHRMeta_ghr") == 0x1000 + index
        assert agent.meta_resolve(index, "phr_phrPtr_value") == 0x200 + index
        assert agent.meta_commit(index, "ras_ssp") == index & 0xF
    state = agent.pointers()
    assert (state.bpu.flag, state.bpu.value) == (1, 0)
    assert (state.pnr.flag, state.pnr.value) == (1, 0)
