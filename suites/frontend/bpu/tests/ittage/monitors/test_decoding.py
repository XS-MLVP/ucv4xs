from __future__ import annotations

from bpuverify.ittage.checker.assertions import allocate


async def test_monitor_decodes_provider_target_and_meta(ittage_agent):
    await ittage_agent.reset()
    prediction = await allocate(ittage_agent)
    assert prediction.meta["provider"]["valid"] == 1
    assert prediction.target == prediction.meta["providerTarget_addr"]
