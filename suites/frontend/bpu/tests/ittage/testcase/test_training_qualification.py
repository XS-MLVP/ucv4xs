"""Only valid taken indirect branches without a RAS pop may train ITTAGE."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.coverage.catalog import ittage_training_qualification_coverage_model
from suites.frontend.bpu.ittage.coverage.catalog import write_ittage_training_qualification_coverage
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.case.definitions import TARGET_B
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ITTAGE-012")
async def test_training_requires_taken_indirect_without_ras_pop(ittage_agent):
    coverage = ittage_training_qualification_coverage_model()
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1

    # BranchType: conditional=1, direct=2, indirect=3.
    # RasAction: none=0, pop=1, push=2, pop-and-push=3.
    rejected = (
        ("invalid_indirect_ignored", {"valid": 0}),
        ("untaken_indirect_ignored", {"taken": 0}),
        ("conditional_ignored", {"branch_type": 1}),
        ("direct_ignored", {"branch_type": 2}),
        ("return_ignored", {"ras_action": 1}),
        ("return_and_call_ignored", {"ras_action": 3}),
    )
    for label, branch in rejected:
        await ittage_agent.train(
            IttageTraining(PC, POSITION, TARGET_B, cold.meta, 1, **branch)
        )
        cold = await ittage_agent.predict(PC)
        assert cold.hit == 0, (label, cold)
        coverage.sample({"branch": label})

    await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_A, cold.meta, 1))
    trained = await ittage_agent.predict(PC)
    assert (trained.hit, trained.target) == (1, TARGET_A)
    coverage.sample({"branch": "indirect_allocates"})

    # Rejected feedback must not rewrite an existing provider either.
    provider_count = trained.meta["providerCnt_value"]
    for label, branch in rejected:
        await ittage_agent.train(
            IttageTraining(PC, POSITION, TARGET_B, trained.meta, 1, **branch)
        )
        trained = await ittage_agent.predict(PC)
        assert (trained.hit, trained.target) == (1, TARGET_A), (label, trained)
        assert trained.meta["providerCnt_value"] == provider_count, (label, trained)

    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1
    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_B, cold.meta, 1, ras_action=2)
    )
    indirect_call = await ittage_agent.predict(PC)
    assert (indirect_call.hit, indirect_call.target) == (1, TARGET_B)
    coverage.sample({"branch": "indirect_call_allocates"})

    coverage.assert_coverage(100.0)
    write_ittage_training_qualification_coverage(coverage, REPO_ROOT)
