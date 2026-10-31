"""Same-bank adjacent feedback under write pressure keeps every entry readable.

A lookup that hits the write buffer returns the newest buffered version, so the
same-bank read/write arbitration only matters once the buffer is under pressure.
An adjacent burst of same-bank feedback therefore drives ``forceWrite``: the
design must retire buffered writes while still answering every lookup with what
it just learned, never with a blank or torn entry.

The eight kernels use one PC and eight distinct folded histories.  Their table-0
tags stay below the implemented eight-bit tag, so this case covers the
read/write arbitration and not the separate ``BPU-UTAGE-007`` tag-width defect.
The independent reference already models the arbitration (``RecentUpdates`` sets
``pressured`` once more than six obligations are outstanding); the case is only
useful if it proves that pressure was actually reached and then relieved.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.checker.assertions import counter
from suites.frontend.bpu.utage.model.addressing import hash_indices
from suites.frontend.bpu.utage.model.addressing import prediction_tag
from suites.frontend.bpu.utage.transaction.types import UtageTraining

HISTORIES = (0, 4, 8, 12, 16, 20, 24, 28)
PRESSURE_DEPTH = 6


def kernels():
    """Eight histories in bank 0 whose table-0 tag is representable."""
    rows = []
    for history in HISTORIES:
        index = hash_indices(PASSING_PC, history)[0]
        tag = prediction_tag(PASSING_PC, history, 0)
        assert index % 4 == 0 and tag < 256, (history, index, tag)
        rows.append((history, index))
    assert len({index for _, index in rows}) == len(rows)
    return tuple(rows)


@pytest.mark.feature("BPU-UTAGE-001")
@pytest.mark.feature("BPU-UTAGE-027")
async def test_adjacent_same_bank_burst_retires_writes_without_losing_entries(utage_agent):
    rows = kernels()
    await utage_agent.reset()
    cold = []
    for history, index in rows:
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 0, folded_history=history)
        assert prediction.hit == 0, (history, prediction)
        assert prediction.meta["readIndex"][0] == index, (history, prediction.meta["readIndex"])
        cold.append((history, prediction))

    # Adjacent beats: every write targets bank 0 while every read also targets
    # bank 0, so writes cannot drain until the buffer is deep enough to force.
    await utage_agent.train_many(tuple(
        UtageTraining(PASSING_PC, POSITION, 1, prediction.meta) for _, prediction in cold))

    updates = utage_agent.reference.model.updates[0]
    depth = len(updates.outstanding)
    assert depth > PRESSURE_DEPTH, depth
    assert updates.pressured is True, depth

    # Every just-learned entry must still read back with its own kernel and the
    # post-allocation counter, even though forced retirement is in flight.
    for history, index in rows:
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 0, folded_history=history)
        entry = prediction.meta["abtbResult"][0]
        assert prediction.meta["readIndex"][0] == index, (history, prediction.meta["readIndex"])
        assert (prediction.hit, prediction.taken) == (1, 1), (history, prediction)
        assert (entry["tableId"], entry["cfiPosition"], counter(prediction)) == (0, POSITION, 4), (
            history, entry)

    # The pressure must actually have relieved: forced writeback retired
    # obligations instead of silently keeping them forever.
    assert len(utage_agent.reference.model.updates[0].outstanding) < depth
