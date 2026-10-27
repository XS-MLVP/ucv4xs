"""Highest-history TAGE provider remains trainable without further allocation."""

from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.checker.assertions import reach_highest_provider
from bpuverify.tage.case.definitions import HIGHEST_TABLE
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-008")
async def test_highest_provider_trains_both_directions_without_disappearing(tage_agent):
    await tage_agent.reset()
    await reach_highest_provider(tage_agent)

    for actual_taken, base_taken, terminal in ((0, 1, 0), (1, 0, 7)):
        prediction = await tage_agent.predict(PC, POSITION, base_taken)
        for _ in range(10):
            predicted_taken = prediction.taken if prediction.valid else base_taken
            await tage_agent.train(
                TageTraining(
                    PC, POSITION, actual_taken, base_taken, prediction.meta,
                    mispredict=int(predicted_taken != actual_taken),
                )
            )
            prediction = await tage_agent.predict(PC, POSITION, base_taken)
            assert prediction.meta["hasProvider"] == 1
            assert prediction.meta["providerTableIdx"] == HIGHEST_TABLE

        assert prediction.meta["providerTakenCtr_value"] == terminal
        assert (prediction.valid, prediction.taken) == (1, actual_taken)
