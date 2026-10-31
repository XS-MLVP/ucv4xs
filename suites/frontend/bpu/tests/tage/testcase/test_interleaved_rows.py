"""Four pending SRAM rows must retain independent provider counter updates."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_interleaved_rows_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_interleaved_rows_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.checker.assertions import prepare_highest_provider
from suites.frontend.bpu.tage.checker.assertions import provider_counter
from suites.frontend.bpu.tage.case.definitions import HIGHEST_TABLE
from suites.frontend.bpu.tage.case.definitions import POSITION
from suites.frontend.bpu.tage.case.definitions import SAME_BANK_PCS


OUTCOMES = (0, 1, 0, 1)


def require_resident(prediction, cell, counter):
    assert prediction.meta["hasProvider"] == 1
    assert prediction.provider_counter_valid == 1
    assert (prediction.meta["providerTableIdx"], prediction.meta["providerWayIdx"]) == cell
    assert provider_counter(prediction) == counter
    assert (prediction.valid, prediction.taken) == (1, int(counter >= 4))


async def check_feedback_mode(agent, coverage, *, adjacent: bool):
    mode = "adjacent" if adjacent else "serial"
    await agent.reset()
    residents = [
        await prepare_highest_provider(agent, pc=pc, position=POSITION, taken=1-outcome)
        for pc, outcome in zip(SAME_BANK_PCS, OUTCOMES)
    ]
    cells = [(p.meta["providerTableIdx"], p.meta["providerWayIdx"]) for p in residents]
    # All four distinct indices occupy one physical table/way write-buffer row.
    # Its capacity is four, so this test does not demand a lossless full miss.
    assert len(set(cells)) == 1
    assert cells[0][0] == HIGHEST_TABLE
    for index, (prediction, cell, outcome) in enumerate(zip(residents, cells, OUTCOMES)):
        require_resident(prediction, cell, 5 if not outcome else 2)
        coverage.sample({"phase": f"{mode}_resident", "context": index})

    feedback = tuple(
        TageBatchTraining(pc, (TageBranchFeedback(
            POSITION, outcome, 1-outcome, prediction.meta, mispredict=1,
        ),))
        for pc, outcome, prediction in zip(SAME_BANK_PCS, OUTCOMES, residents)
    ) * 8
    # Each feedback is opposite to its recorded prediction. Real mispredicts
    # request SRAM reads and defer buffer drain; correct meta-only feedback
    # would not create this pending-row state. Highest providers cannot allocate.
    if adjacent:
        await agent.train_batches(feedback)
    else:
        for transaction in feedback:
            await agent.train_batch(transaction)
    saturated = [await agent.predict(pc, POSITION, outcome) for pc, outcome in zip(SAME_BANK_PCS, OUTCOMES)]
    for index, (prediction, cell, outcome) in enumerate(zip(saturated, cells, OUTCOMES)):
        require_resident(prediction, cell, 7 if outcome else 0)
        coverage.sample({"phase": f"{mode}_saturated", "context": index})

    # Reactivate only the first row. Three other resident counters must remain
    # saturated, even after the pending entries have drained and become shadows.
    await agent.train(TageTraining(
        SAME_BANK_PCS[0], POSITION, 1, 1, saturated[0].meta, mispredict=1,
    ))
    revisited = [await agent.predict(pc, POSITION, outcome) for pc, outcome in zip(SAME_BANK_PCS, OUTCOMES)]
    for index, (prediction, cell, outcome) in enumerate(zip(revisited, cells, OUTCOMES)):
        require_resident(prediction, cell, 1 if index == 0 else (7 if outcome else 0))
        coverage.sample({"phase": f"{mode}_revisit", "context": index})
    return tuple(cells)


@pytest.mark.feature("BPU-TAGE-023")
async def test_four_interleaved_rows_keep_provider_counters_and_revisit_isolation(tage_agent):
    coverage = tage_interleaved_rows_coverage_model()
    adjacent_cells = await check_feedback_mode(tage_agent, coverage, adjacent=True)
    serial_cells = await check_feedback_mode(tage_agent, coverage, adjacent=False)
    assert serial_cells == adjacent_cells
    coverage.assert_coverage(100.0)
    write_tage_interleaved_rows_coverage(coverage, REPO_ROOT)
