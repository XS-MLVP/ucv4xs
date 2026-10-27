"""MicroBTB pipeline responses must retain each request's branch payload."""

from __future__ import annotations

import pytest

from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.checker.assertions import expected_prediction
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import CONDITIONAL
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.case.definitions import INDIRECT


@pytest.mark.feature("BPU-UBTB-013")
async def test_mixed_pc_back_to_back_lookups_keep_exact_payload(ubtb_agent):
    await ubtb_agent.reset()
    for vector in (CONDITIONAL, DIRECT, INDIRECT):
        await train_taken(ubtb_agent, vector)
        await assert_hit(ubtb_agent, vector)

    vectors = (DIRECT, CONDITIONAL, INDIRECT, CONDITIONAL, DIRECT)
    transfers = [
        ubtb_agent.submit_predict(vector.pc, expected=expected_prediction(vector))
        for vector in vectors
    ]
    await ubtb_agent.drain_predictions()
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(transfers), 2))
    assert [await transfer for transfer in transfers] == [
        expected_prediction(vector) for vector in vectors
    ]
