"""A later executed jump corrects an earlier conditional AheadBTB prediction."""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.coverage.catalog import utage_later_branch_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_later_branch_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-013")
async def test_later_nonconditional_branch_trains_earlier_conditional(utage_agent):
    coverage = utage_later_branch_coverage_model()
    later_position = POSITION + 2

    for branch_type, label in ((2, "direct"), (3, "indirect")):
        # A stale AheadBTB conditional at the same position is not evidence
        # for a conditional direction error once the resolved type is a jump.
        await utage_agent.reset()
        same = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert same.hit == 0
        assert same.meta["abtbResult"][0]["valid"] == 1
        assert same.meta["abtbResult"][0]["baseTaken"] == 0
        await utage_agent.train(
            UtageTraining(
                PASSING_PC, POSITION, 1, same.meta,
                mispredict=1, branch_type=branch_type,
            )
        )
        same_after = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert same_after.hit == 0, (label, same_after)
        coverage.sample({"scenario": f"same_{label}_ignored"})

        # Reaching a later jump agrees with an earlier not-taken base: no
        # direction correction needs to be learned.
        await utage_agent.reset()
        correct = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert correct.hit == 0
        await utage_agent.train(
            UtageTraining(
                PASSING_PC, later_position, 1, correct.meta,
                mispredict=0, branch_type=branch_type,
            )
        )
        still_cold = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert still_cold.hit == 0, (label, still_cold)
        coverage.sample({"scenario": f"later_{label}_base_correct"})

        # Reaching the later jump contradicts an earlier taken base. The
        # correction belongs to the earlier conditional position, not to the
        # direct/indirect jump that finally executed.
        await utage_agent.reset()
        wrong = await utage_agent.predict(PASSING_PC, POSITION, 1)
        assert wrong.hit == 0
        assert wrong.meta["abtbResult"][0]["baseTaken"] == 1
        await utage_agent.train(
            UtageTraining(
                PASSING_PC, later_position, 1, wrong.meta,
                mispredict=1, branch_type=branch_type,
            )
        )
        corrected = await utage_agent.predict(PASSING_PC, POSITION, 1)
        assert (corrected.hit, corrected.taken) == (1, 0), (label, corrected)
        assert corrected.meta["abtbResult"][0]["cfiPosition"] == POSITION
        coverage.sample({"scenario": f"later_{label}_suppresses"})

    coverage.assert_coverage(100.0)
    write_utage_later_branch_coverage(coverage, REPO_ROOT)
