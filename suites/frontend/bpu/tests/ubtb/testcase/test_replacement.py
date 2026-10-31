"""MicroBTB full-associative capacity and replacement behavior."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ubtb.checker.assertions import expected_prediction
from suites.frontend.bpu.ubtb.checker.assertions import train_taken
from suites.frontend.bpu.ubtb.case.definitions import NUM_ENTRIES
from suites.frontend.bpu.ubtb.case.definitions import capacity_vectors


@pytest.mark.feature("BPU-UBTB-006")
async def test_capacity_replacement_keeps_exactly_one_payload_per_survivor(
    ubtb_agent,
):
    await ubtb_agent.reset()
    vectors = capacity_vectors()
    for vector in vectors:
        await train_taken(ubtb_agent, vector)

    predictions = [await ubtb_agent.predict(vector.pc) for vector in vectors]
    hits = [
        (vector, prediction)
        for vector, prediction in zip(vectors, predictions, strict=True)
        if prediction.valid
    ]

    assert len(hits) == NUM_ENTRIES
    assert predictions[-1] == expected_prediction(vectors[-1])
    assert all(
        prediction == expected_prediction(vector)
        for vector, prediction in hits
    )
