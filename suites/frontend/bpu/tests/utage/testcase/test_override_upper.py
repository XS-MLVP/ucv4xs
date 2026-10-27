"""Recovery must replay the saved provider table, not just the saved direction.

The existing override cases train through the lower table.  A saved snapshot can
also name the upper table; re-tagging must preserve that saved payload while the
new start PC decides only whether the snapshot still matches.
"""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageBaseBranch, UtageTraining
from bpuverify.utage.case.definitions import PASSING_PC

POSITIONS = (5, 7)
UPPER = PASSING_PC + 0x1000


async def prepare_upper_provider(agent, position):
    """Train one lower and one upper provider at the same logical index.

    The two PCs differ by 0x1000, so their folded history and nine-bit indices
    are identical while the eight-bit lower tag stays representable and
    distinct.  The first training protects the lower row, which is the normal
    public way to make the next allocation select the upper table.
    """
    await agent.reset()
    cold = await agent.predict(PASSING_PC, position, 0)
    assert cold.hit == 0
    await agent.train(UtageTraining(PASSING_PC, position, 1, cold.meta))
    lower = await agent.predict(PASSING_PC, position, 0)
    assert (lower.hit, lower.meta["abtbResult"][0]["tableId"]) == (1, 0)

    cold_upper = await agent.predict(UPPER, position, 0)
    assert cold_upper.hit == 0
    await agent.train(UtageTraining(UPPER, position, 1, cold_upper.meta))
    upper = await agent.predict(UPPER, position, 0)
    entry = upper.meta["abtbResult"][0]
    assert (upper.hit, upper.taken, entry["tableId"], entry["takenCtr_value"]) == (1, 1, 1, 4)
    assert entry["cfiPosition"] == position
    return upper


SLOT2_BRANCHES = (UtageBaseBranch(2, 0), UtageBaseBranch(4, 0), UtageBaseBranch(6, 0), None)


async def prepare_slot2_upper_provider(agent):
    """Put the upper-table provider in slot 2 of a real three-branch beat.

    A single-branch beat can only ever hit slot 0: its slot-2 fallback position
    is ``position + 2``, so a table entry trained at ``position`` can never be
    the slot-2 provider.  The lower table is first made useful at an unused
    position (1), which is what forces the next correct-but-new outcome
    (position 6) into the upper table.  Nothing here fabricates a hit: every
    lookup and every training carries real branch positions.
    """

    await agent.reset()
    cold = await agent.predict(PASSING_PC, 1, 0)
    assert cold.hit == 0
    await agent.train(UtageTraining(PASSING_PC, 1, 1, cold.meta))
    lower = await agent.predict(PASSING_PC, 1, 0)
    assert (lower.hit, lower.meta["abtbResult"][0]["tableId"]) == (1, 0)

    upper_cold = await agent.predict_branches(PASSING_PC, SLOT2_BRANCHES)
    assert upper_cold.hit == 0
    await agent.train(UtageTraining(PASSING_PC, 6, 1, upper_cold.meta))
    trained = await agent.predict_branches(PASSING_PC, SLOT2_BRANCHES)
    slot = trained.meta["abtbResult"][2]
    # The overall ``hit`` of a prediction is slot 0's hit; the provider under
    # test lives in slot 2, so it must be asserted on that slot.
    assert (slot["hit"], slot["tableId"], slot["cfiPosition"]) == (1, 1, 6)
    assert slot["predTaken"] == 1
    return trained


@pytest.mark.feature("BPU-UTAGE-008")
@pytest.mark.feature("BPU-UTAGE-009")
@pytest.mark.parametrize("stage", ("s2", "s3"))
async def test_override_replays_an_upper_table_provider_from_a_nonzero_slot(utage_agent, stage):
    """A saved upper-table provider in slot 2 is replayed by its saved table.

    The three-branch beat makes position 6 the slot-2 provider in the upper
    table.  The recovery re-presents the same AheadBTB beat: the saved vector
    (not a single-branch re-read) must still name table 1 for slot 2, keep the
    saved counter and position, and drive the public direction from that
    counter.  The raw hit verdict is not asserted; it is still compared field
    by field by the reference model.
    """

    trained = await prepare_slot2_upper_provider(utage_agent)
    assert trained.meta["abtbResult"][2]["takenCtr_value"] == 4

    replayed = await utage_agent.recover_prediction_branches(
        PASSING_PC, SLOT2_BRANCHES, stage=stage, override_pc=PASSING_PC)
    slot = replayed.meta["abtbResult"][2]
    # The replay is a raw-direction contract for this re-presented beat: the
    # saved upper-table identity and counter survive even though the sampled
    # stage no longer carries the upstream branch validity.  ``valid``/``hit``
    # are therefore not asserted, but the reference model still compares them.
    assert (slot["tableId"], slot["cfiPosition"]) == (1, 6)
    assert (slot["takenCtr_value"], slot["predTaken"]) == (4, 1)
    assert replayed.taken == 1


@pytest.mark.feature("BPU-UTAGE-008")
@pytest.mark.feature("BPU-UTAGE-009")
@pytest.mark.parametrize("stage", ("s2", "s3"))
@pytest.mark.parametrize("position", POSITIONS)
async def test_override_replays_a_saved_upper_table_provider(utage_agent, stage, position):
    await prepare_upper_provider(utage_agent, position)

    # Same override start PC: the saved upper-table provider is replayed with
    # its own direction and counter, not re-derived from a fresh lookup.
    replayed = await utage_agent.recover_prediction(
        UPPER, position, 0, stage=stage, override_pc=UPPER)
    entry = replayed.meta["abtbResult"][0]
    assert (replayed.hit, replayed.taken) == (1, 1)
    assert (entry["tableId"], entry["takenCtr_value"], entry["cfiPosition"]) == (1, 4, position)

    # Different override start PC changes only the tag comparison.  A retag
    # miss is not a defined provider payload, but the raw direction still comes
    # from the saved snapshot; only the hit verdict may change.
    retagged = await utage_agent.recover_prediction(
        UPPER, position, 0, stage=stage, override_pc=UPPER + 0x20)
    assert (retagged.hit, retagged.taken) == (0, 1)
