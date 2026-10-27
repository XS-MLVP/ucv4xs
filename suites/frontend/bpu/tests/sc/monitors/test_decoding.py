from __future__ import annotations

from bpuverify.sc.checker.assertions import learn


async def test_monitor_decodes_decision_and_threshold_metadata(sc_agent):
    await sc_agent.reset()
    prediction = await learn(sc_agent, 1)
    assert prediction.used == 1
    assert prediction.meta["useScPred"][0] == 1
    assert prediction.meta["sumAboveThres"][0] == 1
