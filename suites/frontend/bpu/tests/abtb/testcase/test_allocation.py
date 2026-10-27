"""AheadBTB allocation and non-allocation rules."""

from __future__ import annotations

import pytest

from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NOT_TAKEN
from bpuverify.abtb.case.definitions import TRAINING_VECTORS


@pytest.mark.feature("BPU-ABTB-002")
@pytest.mark.parametrize("vector", TRAINING_VECTORS)
async def test_taken_branch_types_allocate_to_a_bank(abtb_agent, vector):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(vector.pc)
    await train_taken(abtb_agent, vector, cold.meta)

    assert_vector_hit(await abtb_agent.predict(vector.pc), vector)


@pytest.mark.feature("BPU-ABTB-003")
async def test_not_taken_miss_does_not_allocate(abtb_agent):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(NOT_TAKEN.pc)
    await abtb_agent.train(
        AbtbTraining(
            NOT_TAKEN.pc,
            NOT_TAKEN.target,
            0,
            NOT_TAKEN.position,
            NOT_TAKEN.branch_type,
            cold.meta,
        )
    )

    assert_miss(await abtb_agent.predict(NOT_TAKEN.pc))
