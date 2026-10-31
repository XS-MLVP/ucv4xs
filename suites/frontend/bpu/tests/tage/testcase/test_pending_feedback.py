"""Repeated metadata-only FTQ feedback exercises same-provider forwarding.

Correct provider-only feedback does not read SRAM, so this scenario alone
does not establish that multiple write-buffer indices are pending together.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_pending_feedback_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_pending_feedback_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.checker.assertions import allocate
from suites.frontend.bpu.tage.checker.assertions import provider_counter
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-022")
async def test_consecutive_feedback_saturates_pending_provider(tage_agent):
    coverage = tage_pending_feedback_coverage_model()
    await tage_agent.reset()
    weak = await allocate(tage_agent)
    assert provider_counter(weak) == 4
    await tage_agent.train(
        TageTraining(PC, POSITION, 1, 1, weak.meta, mispredict=0)
    )
    resident = await tage_agent.predict(PC, POSITION, 1)
    assert resident.meta["hasProvider"] == 1
    assert provider_counter(resident) == 5
    cell = resident.meta["providerTableIdx"], resident.meta["providerWayIdx"]
    coverage.sample({"phase": "resident"})

    feedback = TageBatchTraining(
        PC,
        (TageBranchFeedback(
            POSITION, 1, 1, resident.meta, mispredict=0
        ),),
    )
    await tage_agent.train_batches((feedback,) * 8)
    saturated = await tage_agent.predict(PC, POSITION, 1)
    assert saturated.meta["hasProvider"] == 1
    assert (saturated.meta["providerTableIdx"], saturated.meta["providerWayIdx"]) == cell
    assert provider_counter(saturated) == 7
    assert (saturated.valid, saturated.taken) == (1, 1)
    coverage.sample({"phase": "saturated_after_burst"})

    coverage.assert_coverage(100.0)
    write_tage_pending_feedback_coverage(coverage, REPO_ROOT)
