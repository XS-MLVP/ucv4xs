"""MainBTB pipeline association must use each request's own payload."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.definitions import DIRECT
from suites.frontend.bpu.mbtb.case.definitions import MISS_PC


@pytest.mark.feature("BPU-MBTB-012")
async def test_mixed_pc_back_to_back_lookups_keep_target_and_position(mbtb_agent):
    await mbtb_agent.reset()
    other = BranchVector(MISS_PC, 0x4000_6780, 3, 3)
    for vector in (DIRECT, other):
        cold = await mbtb_agent.predict(vector.pc)
        await train(mbtb_agent, vector, cold.meta_entries)
        assert_vector_hit(await mbtb_agent.predict(vector.pc), vector)

    vectors = (DIRECT, other, DIRECT, other)
    transfers = [mbtb_agent.submit_predict(vector.pc) for vector in vectors]
    await mbtb_agent.drain_predictions()
    predictions = [await transfer for transfer in transfers]
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(transfers), 2))
    for vector, prediction in zip(vectors, predictions):
        assert_vector_hit(prediction, vector)
