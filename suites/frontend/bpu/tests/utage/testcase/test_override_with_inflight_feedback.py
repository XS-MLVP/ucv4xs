"""Recovery must replay its saved snapshot even when feedback lands mid-flight.

The existing override cases train first and then recover, so the saved snapshot
and the current table already agree; a re-read of current SRAM would look
identical.  This case submits the recovery *before* the adjacent feedback pulse
and requires the response to keep the pre-feedback counter, while a fresh lookup
in the same program must observe the post-feedback state.  The two observations
differing is what proves the recovery replayed a snapshot instead of re-reading
the current candidate.

The recovery response is deliberately NOT compared against a fresh lookup as an
equality: features 008/009 define override as reusing an *older* saved age, so
equality with the newest read is not an obligation.  The only equality asserted
here is against the snapshot that existed when the recovery was submitted.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.checker.assertions import counter
from suites.frontend.bpu.utage.transaction.types import UtageTraining

WARM_COUNTER = 5
TRAINED_COUNTER = 3


async def warm(agent):
    cold = await agent.predict(PASSING_PC, POSITION, 0)
    assert cold.hit == 0
    await agent.train(UtageTraining(PASSING_PC, POSITION, 1, cold.meta))
    current = await agent.predict(PASSING_PC, POSITION, 0)
    await agent.train(UtageTraining(PASSING_PC, POSITION, 1, current.meta, mispredict=0))
    trained = await agent.predict(PASSING_PC, POSITION, 0)
    entry = trained.meta["abtbResult"][0]
    assert (trained.hit, trained.taken, counter(trained)) == (1, 1, WARM_COUNTER), trained
    assert entry["tableId"] == 0, entry
    return trained


@pytest.mark.feature("BPU-UTAGE-008")
@pytest.mark.feature("BPU-UTAGE-009")
@pytest.mark.parametrize("stage", ("s2", "s3"))
async def test_recovery_replays_the_saved_snapshot_when_feedback_lands_in_flight(utage_agent, stage):
    await utage_agent.reset()
    source = await warm(utage_agent)

    # Submit the recovery first, then let one genuine not-taken result land
    # while it is still in flight.  The response must still describe the saved
    # snapshot; it must not re-read the table the feedback just modified.
    replay = utage_agent.submit_predict(
        PASSING_PC, POSITION, 1, override=stage, override_pc=PASSING_PC)
    await utage_agent.train(UtageTraining(
        PASSING_PC, POSITION, 0, source.meta, mispredict=1))

    replayed = await replay
    assert replayed.hit == 1, replayed
    assert (replayed.taken, counter(replayed)) == (1, WARM_COUNTER), replayed
    assert replayed.meta["abtbResult"][0]["tableId"] == 0, replayed

    # The feedback really landed: a fresh lookup sees the new direction.  If it
    # did not, the assertion above would be vacuous.
    fresh = await utage_agent.predict(PASSING_PC, POSITION, 1)
    assert fresh.taken == 0, fresh
    assert counter(fresh) == TRAINED_COUNTER, fresh
    assert (replayed.taken, counter(replayed)) != (fresh.taken, counter(fresh)), (
        "recovery and the fresh lookup must differ when feedback lands after the snapshot")
