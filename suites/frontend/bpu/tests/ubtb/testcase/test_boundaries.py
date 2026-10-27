"""MicroBTB partial-tag and payload boundaries."""

from __future__ import annotations

import pytest

from bpuverify.ubtb.transaction.types import UbtbPrediction
from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.case.definitions import PARTIAL_TAG_SPAN
from bpuverify.ubtb.case.definitions import PARTIAL_TARGET_SPAN
from bpuverify.ubtb.case.definitions import boundary_vectors


@pytest.mark.feature("BPU-UBTB-008")
async def test_position_and_target_lower_boundaries_round_trip(ubtb_agent):
    await ubtb_agent.reset()
    for vector in boundary_vectors():
        await train_taken(ubtb_agent, vector)
        await assert_hit(ubtb_agent, vector)


@pytest.mark.feature("BPU-UBTB-008")
async def test_partial_tag_alias_reconstructs_target_from_lookup_region(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)
    alias_pc = DIRECT.pc + PARTIAL_TAG_SPAN
    alias_region = alias_pc & ~(PARTIAL_TARGET_SPAN - 1)
    target_lower = DIRECT.target & (PARTIAL_TARGET_SPAN - 1)

    assert await ubtb_agent.predict(alias_pc) == UbtbPrediction(
        valid=1,
        taken=1,
        target=alias_region | target_lower,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
