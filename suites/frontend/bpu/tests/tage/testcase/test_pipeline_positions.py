"""A trained provider must follow its position through the lookup pipeline."""

from __future__ import annotations

import pytest

from bpuverify.tage.checker.assertions import allocate
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-011")
async def test_interleaved_positions_keep_provider_association(tage_agent):
    await tage_agent.reset()
    trained = await allocate(tage_agent)
    assert trained.meta["hasProvider"] == 1
    other_position = POSITION + 1
    cold_other = await tage_agent.predict(PC, other_position, 0)
    assert cold_other.meta["hasProvider"] == 0

    positions = (POSITION, other_position, POSITION, other_position)
    transfers = [tage_agent.submit_predict(PC, position, 0) for position in positions]
    await tage_agent.drain_predictions()
    predictions = [await transfer for transfer in transfers]
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(transfers), 2))
    assert [prediction.meta["hasProvider"] for prediction in predictions] == [
        1, 0, 1, 0
    ]
