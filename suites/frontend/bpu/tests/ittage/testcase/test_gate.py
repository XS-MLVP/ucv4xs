from __future__ import annotations

import pytest

from bpuverify.ittage.checker.assertions import allocate
from bpuverify.ittage.case.definitions import PC


@pytest.mark.feature("BPU-ITTAGE-004")
async def test_enable_gate_suppresses_existing_hit(ittage_agent):
    await ittage_agent.reset()
    await allocate(ittage_agent)
    await ittage_agent.set_enabled(False)
    assert (await ittage_agent.predict(PC)).hit == 0
    await ittage_agent.set_enabled(True)
    assert (await ittage_agent.predict(PC)).hit == 1
