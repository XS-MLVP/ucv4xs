"""Explicit-only probe: ITTAGE learning from an unserved original query snapshot."""
import json

from bpuverify.ittage.transaction.types import IttageTraining

PC = 0x40001800
POSITION = 4
TARGET = 0x40002800


async def test_probe_unserved_training(ittage_agent, request):
    await ittage_agent.reset()
    enabled_cold = await ittage_agent.predict(PC)
    await ittage_agent.set_enabled(False)
    unserved = await ittage_agent.predict(PC)
    await ittage_agent.set_enabled(True)
    fresh = await ittage_agent.predict(PC)
    training = IttageTraining(PC, POSITION, TARGET, unserved.meta, 1)
    await ittage_agent.train(training)
    after = await ittage_agent.predict(PC)
    evidence = dict(
        enabled_cold=dict(hit=enabled_cold.hit, target=hex(enabled_cold.target),
                          meta=enabled_cold.meta),
        unserved=dict(hit=unserved.hit, target=hex(unserved.target),
                      meta=unserved.meta),
        fresh=dict(hit=fresh.hit, target=hex(fresh.target), meta=fresh.meta),
        after=dict(hit=after.hit, target=hex(after.target), meta=after.meta),
    )
    request.node.user_properties.append(
        ("unserved_training_probe", json.dumps(evidence, ensure_ascii=False))
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
