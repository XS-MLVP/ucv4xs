"""Prediction payload and metadata are captured in one immutable object."""

from __future__ import annotations

from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import DIRECT


async def test_monitor_decodes_entry_and_meta_from_same_response(mbtb_agent):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(DIRECT.pc)
    await train(mbtb_agent, DIRECT, cold.meta_entries)
    prediction = await mbtb_agent.predict(DIRECT.pc)

    assert_vector_hit(prediction, DIRECT)
    assert any(
        item["rawHit"] and item["position"] == DIRECT.position
        for bank in prediction.meta_entries
        for item in bank
    )
