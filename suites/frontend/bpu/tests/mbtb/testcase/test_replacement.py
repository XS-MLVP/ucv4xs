"""MainBTB same-set replacement and payload isolation."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import NUM_WAYS
from bpuverify.mbtb.case.definitions import conflict_vectors


@pytest.mark.feature("BPU-MBTB-006")
async def test_fifth_same_physical_set_entry_replaces_one_way(mbtb_agent):
    await mbtb_agent.reset()
    vectors = conflict_vectors()
    for vector in vectors:
        cold = await mbtb_agent.predict(vector.pc)
        await train(mbtb_agent, vector, cold.meta_entries)

    predictions = [await mbtb_agent.predict(vector.pc) for vector in vectors]
    hits = [
        (vector, prediction)
        for vector, prediction in zip(vectors, predictions, strict=True)
        if any(entry.valid for entry in prediction.entries)
    ]

    assert len(hits) == NUM_WAYS
    assert any(entry.valid for entry in predictions[-1].entries)
    for vector, prediction in hits:
        assert_vector_hit(prediction, vector)
