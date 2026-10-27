"""MainBTB entry allocation and payload behavior."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BRANCH_TYPES
from bpuverify.mbtb.case.definitions import coexistence_vectors


@pytest.mark.feature("BPU-MBTB-002")
async def test_multiple_positions_coexist_in_one_fetch_block(mbtb_agent):
    await mbtb_agent.reset()
    vectors = coexistence_vectors()
    prediction = await mbtb_agent.predict(vectors[0].pc)
    for vector in vectors:
        await train(mbtb_agent, vector, prediction.meta_entries)
        prediction = await mbtb_agent.predict(vector.pc)

    for vector in vectors:
        assert_vector_hit(prediction, vector)


@pytest.mark.feature("BPU-MBTB-003")
@pytest.mark.parametrize("vector", BRANCH_TYPES)
async def test_branch_type_target_and_position_round_trip(mbtb_agent, vector):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(vector.pc)
    await train(mbtb_agent, vector, cold.meta_entries)

    assert_vector_hit(await mbtb_agent.predict(vector.pc), vector)
