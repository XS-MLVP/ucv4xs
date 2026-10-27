"""MicroTAGE pipeline recovery must reuse the selected saved prediction."""

from __future__ import annotations

import pytest

from bpuverify.utage.checker.assertions import allocate
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


async def _check_override(utage_agent, stage: str) -> None:
    await utage_agent.reset()
    trained = await allocate(utage_agent, PASSING_PC, POSITION)
    assert (trained.hit, trained.taken) == (1, 1)

    # The override must preserve the trained PC's saved A2/A3 prediction.
    replayed = await utage_agent.recover_prediction(
        PASSING_PC,
        POSITION,
        0,
        stage=stage,
        override_pc=PASSING_PC,
    )
    assert (replayed.hit, replayed.taken) == (1, 1), replayed

    # The saved data is re-tagged against overrideStartPc, not newStartPc.
    # Keeping the ordinary lookup PC fixed isolates that selection rule.
    retagged = await utage_agent.recover_prediction(
        PASSING_PC,
        POSITION,
        0,
        stage=stage,
        override_pc=PASSING_PC + 0x20,
    )
    assert retagged.hit == 0, retagged


@pytest.mark.feature("BPU-UTAGE-008")
async def test_s2_override_reuses_a2_prediction_snapshot(utage_agent):
    await _check_override(utage_agent, "s2")


@pytest.mark.feature("BPU-UTAGE-009")
async def test_s3_override_reuses_a3_prediction_snapshot(utage_agent):
    await _check_override(utage_agent, "s3")
