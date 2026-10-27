"""SC training qualification must preserve state for ineligible feedback."""

from __future__ import annotations

import pytest

from bpuverify.sc.transaction.types import ScTraining
from bpuverify.sc.coverage.catalog import sc_training_qualification_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_training_qualification_coverage
from bpuverify.sc.checker.assertions import learn
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.sc.case.definitions import TAKEN_ATTEMPTS
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-011")
async def test_ineligible_training_feedback_preserves_learned_correction(sc_agent):
    coverage = sc_training_qualification_coverage_model()
    await sc_agent.reset()
    learned = await learn(sc_agent, 0)
    assert (learned.used, learned.taken) == (1, 0)
    assert learned.meta["tagePredValid"][0] == 1
    coverage.sample({"phase": "learned_not_taken"})

    provider_invalid = await sc_agent.predict(
        PC, POSITION, TAGE_COUNTER, provider_valid=0
    )
    assert provider_invalid.used == 0
    assert provider_invalid.meta["tagePredValid"][0] == 0
    scenarios = (
        (
            "mbtb_miss_ignored",
            ScTraining(PC, POSITION, 1, learned.meta, mbtb_hit=0),
        ),
        (
            "nonconditional_ignored",
            ScTraining(PC, POSITION, 1, learned.meta, branch_type=2),
        ),
        (
            "provider_invalid_ignored",
            ScTraining(PC, POSITION, 1, provider_invalid.meta),
        ),
    )
    for phase, transaction in scenarios:
        for _ in range(TAKEN_ATTEMPTS):
            await sc_agent.train(transaction)
        retained = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
        assert (retained.used, retained.taken) == (1, 0), (phase, retained)
        coverage.sample({"phase": phase})

    retrained = await learn(sc_agent, 1)
    assert (retrained.used, retrained.taken) == (1, 1)
    coverage.sample({"phase": "qualified_taken_learned"})
    coverage.assert_coverage(100.0)
    write_sc_training_qualification_coverage(coverage, REPO_ROOT)
