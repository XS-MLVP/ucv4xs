from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.checker.assertions import allocate
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import PC_ALIAS
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-005")
async def test_weak_provider_falls_back_then_strengthened_provider_wins(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)

    assert prediction.meta["hasProvider"] == 1
    assert prediction.meta["useProvider"] == 0
    assert prediction.meta["altOrBasePred"] == 0
    assert prediction.valid == 0

    for _ in range(4):
        await tage_agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta))
        prediction = await tage_agent.predict(PC, POSITION, 0)
        if prediction.meta["useProvider"]:
            break

    assert prediction.meta["useProvider"] == 1
    assert prediction.valid == 1
    assert prediction.taken == 1


@pytest.mark.feature("BPU-TAGE-006")
async def test_useful_counter_increases_when_provider_adds_value(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    trace = [prediction.meta["providerUsefulCtr_value"]]

    for _ in range(4):
        await tage_agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta))
        prediction = await tage_agent.predict(PC, POSITION, 0)
        trace.append(prediction.meta["providerUsefulCtr_value"])

    assert trace == sorted(trace)
    assert trace[-1] > trace[0]


@pytest.mark.feature("BPU-TAGE-007")
async def test_pc_tag_isolation_preserves_provider_across_other_lookup(tage_agent):
    await tage_agent.reset()
    await allocate(tage_agent)
    original = await tage_agent.predict(PC, POSITION, 0)
    other = await tage_agent.predict(PC_ALIAS, POSITION, 0)
    revisited = await tage_agent.predict(PC, POSITION, 0)

    assert original.meta["hasProvider"] == 1
    assert other.meta["hasProvider"] == 0
    assert revisited.meta["hasProvider"] == 1
