"""A redirect revokes the in-flight MicroTAGE window, not the learned record.

``io.redirect`` was decoded by the monitor and consumed by the independent model,
but the lookup driver never drove it: the field was not even in the fast-lookup
bundle.  This case drives it for real and states the obligation:

* the revoked window publishes no hit and no valid AheadBTB slot;
* the learned entry survives and still serves the next lookup with its original
  provider table, position and counter;
* without the redirect the same program keeps the hit (control).
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.transaction.types import UtageTraining

OTHER_PC = PASSING_PC + 0x40


async def install(agent):
    cold = await agent.predict(PASSING_PC, POSITION, 0)
    assert cold.hit == 0
    await agent.train(UtageTraining(PASSING_PC, POSITION, 1, cold.meta))
    warm = await agent.predict(PASSING_PC, POSITION, 0)
    entry = warm.meta["abtbResult"][0]
    assert (warm.hit, warm.taken) == (1, 1), warm
    assert (entry["tableId"], entry["cfiPosition"], entry["takenCtr_value"]) == (0, POSITION, 4), entry
    return entry


def slot_valid(prediction):
    return tuple(slot["valid"] for slot in prediction.meta["abtbResult"])


@pytest.mark.feature("BPU-UTAGE-026")
async def test_redirect_flushes_the_inflight_window_and_keeps_the_learned_record(utage_agent):
    await utage_agent.reset()
    entry = await install(utage_agent)

    # Control: the identical program without a redirect must keep the hit, so
    # the flush below cannot be explained by the second lookup alone.
    control_first = utage_agent.submit_predict(PASSING_PC, POSITION, 0)
    control_other = utage_agent.submit_predict(OTHER_PC, POSITION + 1, 0)
    control = await control_first
    await control_other
    assert control.hit == 1 and slot_valid(control)[0] == 1, control

    # Real redirect: B's S0 pulse carries it while A is still in flight.
    first = utage_agent.submit_predict(PASSING_PC, POSITION, 0)
    second = utage_agent.submit_predict(OTHER_PC, POSITION + 1, 0, redirect=True)

    revoked = await first
    assert revoked.hit == 0, revoked
    assert slot_valid(revoked) == (0, 0, 0, 0), revoked
    assert all(slot["hit"] == 0 for slot in revoked.meta["abtbResult"]), revoked
    await second

    # The redirect revokes publication, not learning: the same entry still
    # serves with its original table, position and counter.
    after = await utage_agent.predict(PASSING_PC, POSITION, 0)
    restored = after.meta["abtbResult"][0]
    assert (after.hit, after.taken) == (1, 1), after
    assert (restored["tableId"], restored["cfiPosition"], restored["takenCtr_value"]) == (
        entry["tableId"], entry["cfiPosition"], entry["takenCtr_value"]), after

    # A redirect with an idle pipeline neither creates nor destroys a record.
    idle = utage_agent.submit_predict(PASSING_PC, POSITION, 0, redirect=True)
    await utage_agent.drain_predictions()
    await idle
    settled = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert settled.hit == 1, settled
