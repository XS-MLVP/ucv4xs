"""Back-to-back AheadBTB requests must retain their individual payloads."""

from __future__ import annotations

import pytest

from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import TRAINING_VECTORS
from bpuverify.abtb.case.definitions import hash_bank_vectors


@pytest.mark.feature("BPU-ABTB-022")
async def test_mixed_pc_back_to_back_requests_keep_payload_association(abtb_agent):
    await abtb_agent.reset()
    for vector in TRAINING_VECTORS:
        cold = await abtb_agent.predict(vector.pc)
        await train_taken(abtb_agent, vector, cold.meta)
        assert_vector_hit(await abtb_agent.predict(vector.pc), vector)

    vectors = (*TRAINING_VECTORS, *reversed(TRAINING_VECTORS))
    transfers = [abtb_agent.submit_predict(vector.pc) for vector in vectors]
    await abtb_agent.drain_predictions()
    predictions = [await transfer for transfer in transfers]
    observed_positions = [
        tuple(entry.position for entry in prediction.entries if entry.valid)
        for prediction in predictions
    ]
    assert observed_positions == [(vector.position,) for vector in vectors], [
        (transfer.accepted_event.tick, transfer.completed_event.tick, positions)
        for transfer, positions in zip(transfers, observed_positions)
    ]
    for vector, prediction in zip(vectors, predictions):
        assert_vector_hit(prediction, vector)


@pytest.mark.feature("BPU-ABTB-023")
async def test_mixed_history_back_to_back_requests_keep_bank_and_target(abtb_agent):
    await abtb_agent.reset()
    contexts = hash_bank_vectors()
    for path_hash, vector in contexts:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        await train_taken(abtb_agent, vector, cold.meta)
        assert_vector_hit(
            await abtb_agent.predict(vector.pc, path_hash=path_hash), vector
        )

    sequence = (*contexts, *reversed(contexts))
    transfers = [
        abtb_agent.submit_predict(vector.pc, path_hash=path_hash)
        for path_hash, vector in sequence
    ]
    await abtb_agent.drain_predictions()
    for (path_hash, vector), transfer in zip(sequence, transfers):
        prediction = await transfer
        assert prediction.meta["bankMask"] == 1 << path_hash
        assert_vector_hit(prediction, vector)
