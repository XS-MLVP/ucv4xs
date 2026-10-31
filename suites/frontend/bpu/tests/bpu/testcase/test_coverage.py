from __future__ import annotations

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.coverage.catalog import bpu_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_coverage
from suites.frontend.bpu.bpu.checker.assertions import train_direct_branch
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import PREDICTION_LIMIT
from suites.frontend.bpu.bpu.case.definitions import REDIRECT_PC
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_bpu_functional_coverage_closes_defined_bins(bpu_agent):
    coverage = bpu_coverage_model()
    await bpu_agent.reset(PC)
    cold = await bpu_agent.next_transaction(start_pc=PC)
    assert cold.prediction.taken == 0
    coverage.sample({"phase": "cold", "taken": cold.prediction.taken, "control": "stream"})
    meta, trained = await train_direct_branch(bpu_agent, cold)
    assert trained.taken == 1
    coverage.sample({"phase": "trained", "taken": trained.taken, "control": "redirect"})
    await bpu_agent.set_enabled(False)
    await bpu_agent.redirect(BpuRedirect(PC, meta.redirect))
    _, disabled = await bpu_agent.next_prediction(start_pc=PC, limit=PREDICTION_LIMIT)
    assert disabled.taken == 0
    coverage.sample({"phase": "disabled", "taken": disabled.taken, "control": "redirect"})
    stalled = await bpu_agent.redirect_while_backpressured(
        BpuRedirect(REDIRECT_PC, meta.redirect)
    )
    assert stalled.stalled_prediction.start_pc != REDIRECT_PC
    assert stalled.redirected_prediction.start_pc == REDIRECT_PC
    assert stalled.first_accepted_prediction.start_pc == REDIRECT_PC
    assert stalled.first_accepted_prediction.taken == 0
    coverage.sample(
        {
            "phase": "disabled",
            "taken": stalled.first_accepted_prediction.taken,
            "control": "redirect_stalled",
        }
    )
    coverage.assert_coverage(100.0)
    write_bpu_coverage(coverage, REPO_ROOT)
