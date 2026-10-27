"""MainBTB SRAM reset and cold lookup."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-MBTB-001")
async def test_reset_completes_before_cold_lookup(mbtb_agent):
    waited = await mbtb_agent.reset()
    cold = await mbtb_agent.predict(DIRECT.pc)

    assert waited < 256
    assert_miss(cold)
