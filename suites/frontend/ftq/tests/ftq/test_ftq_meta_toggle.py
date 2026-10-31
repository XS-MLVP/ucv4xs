"""FTQ metadata payload breadth: every stored bit accepts one and zero."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.ftq.transaction.types import PredictionSpec

pytestmark = pytest.mark.feature("FTQ-TOP-017")


async def _write_lap(agent, fields: dict[str, int]) -> None:
    specs = [PredictionSpec(0x8000_0000 + index * 0x20, meta=fields)
             for index in range(64)]
    await agent.allocate(specs, consume=True)


async def test_every_metadata_bit_accepts_all_ones_and_all_zeros(ftq_agent):
    agent = ftq_agent
    ones = agent.meta_payload(1)
    await _write_lap(agent, ones)
    for index in range(64):
        assert agent.meta_redirect(index, "phr_phrPtr_value") == 0x3FF
        assert agent.meta_redirect(index, "commonHRMeta_ghr") == 0xFFFF
        assert agent.meta_redirect(index, "ras_topRetAddr_addr") == (1 << 50) - 1

    # Reset records the 1->0 transition for every metadata bit; the next lap
    # holds zero and proves the queue stores the opposite direction as well.
    await agent.reset()
    await _write_lap(agent, agent.meta_payload(0))
    for index in range(64):
        assert agent.meta_redirect(index, "phr_phrPtr_value") == 0
        assert agent.meta_redirect(index, "commonHRMeta_ghr") == 0
        assert agent.meta_redirect(index, "ras_topRetAddr_addr") == 0
