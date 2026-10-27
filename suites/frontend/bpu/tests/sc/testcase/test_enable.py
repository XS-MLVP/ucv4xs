"""The global gate must suppress SC use and training without erasing state."""

from __future__ import annotations

import pytest

from bpuverify.sc.transaction.types import ScTraining
from bpuverify.sc.coverage.catalog import sc_enable_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_enable_coverage
from bpuverify.sc.checker.assertions import learn
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-010")
async def test_disable_suppresses_use_and_training_without_erasing_state(sc_agent):
    coverage = sc_enable_coverage_model()
    await sc_agent.reset()
    trained = await learn(sc_agent, 1)
    assert (trained.used, trained.taken) == (1, 1)
    coverage.sample({"phase": "trained"})

    await sc_agent.set_enabled(False)
    disabled = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    assert disabled.used == 0
    coverage.sample({"phase": "disabled"})

    for _ in range(NOT_TAKEN_ATTEMPTS):
        await sc_agent.train(ScTraining(PC, POSITION, 0, trained.meta))

    await sc_agent.set_enabled(True)
    retained = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    assert (retained.used, retained.taken) == (1, 1)
    coverage.sample({"phase": "retained"})

    for _ in range(NOT_TAKEN_ATTEMPTS):
        await sc_agent.train(ScTraining(PC, POSITION, 0, trained.meta))
    retrained = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    assert (retrained.used, retrained.taken) == (1, 0)
    coverage.sample({"phase": "retrained"})
    coverage.assert_coverage(100.0)
    write_sc_enable_coverage(coverage, REPO_ROOT)
