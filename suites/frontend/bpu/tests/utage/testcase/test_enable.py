"""MicroTAGE disable gates delayed fastTrain and freezes prediction state."""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.coverage.catalog import utage_enable_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_enable_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-012")
async def test_global_disable_blocks_fast_train_and_holds_lookup_state(utage_agent):
    coverage = utage_enable_coverage_model()
    await utage_agent.reset()
    cold = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert cold.hit == 0
    allocation = UtageTraining(PASSING_PC, POSITION, 1, cold.meta)

    await utage_agent.set_enabled(False)
    await utage_agent.train(allocation)
    await utage_agent.set_enabled(True)
    still_cold = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert still_cold.hit == 0
    coverage.sample({"phase": "disabled_train_blocked"})

    await utage_agent.train(allocation)
    trained = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (trained.hit, trained.taken) == (1, 1)
    coverage.sample({"phase": "enabled_train_allocates"})

    await utage_agent.set_enabled(False)
    held = await utage_agent.predict(
        PASSING_PC, POSITION, 0, folded_history=0b1000
    )
    assert (held.hit, held.taken) == (trained.hit, trained.taken)
    coverage.sample({"phase": "disabled_lookup_held"})

    await utage_agent.set_enabled(True)
    other_history = await utage_agent.predict(
        PASSING_PC, POSITION, 0, folded_history=0b1000
    )
    assert other_history.hit == 0
    retained = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (retained.hit, retained.taken) == (1, 1)
    coverage.sample({"phase": "reenabled_contexts"})
    coverage.assert_coverage(100.0)
    write_utage_enable_coverage(coverage, REPO_ROOT)
