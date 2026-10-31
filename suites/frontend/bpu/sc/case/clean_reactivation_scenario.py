"""Learn four rows, drain, and rewrite one selected way of an existing row."""
from suites.frontend.bpu.models.configuration import *

from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.checker.assertions import sc_row_indices
from suites.frontend.bpu.sc.case.bias_selector_scenario import read_bias_grid
from suites.frontend.bpu.sc.case.bias_selector_scenario import require_bias_grid
from suites.frontend.bpu.sc.case.bias_selector_scenario import send_bias_feedback
from suites.frontend.bpu.sc.case.definitions import MASKED_POSITIONS
from suites.frontend.bpu.sc.case.definitions import SAME_BANK_PCS


async def check_clean_reactivation_mode(agent, coverage, *, adjacent):
    await agent.reset()
    mode = "adjacent" if adjacent else "serial"
    predictions = await read_bias_grid(agent)
    routes = tuple(sc_row_indices(predictions[row, 0]) for row in range(4))
    for indices in zip(*routes, strict=True):
        assert len(set(indices)) == 4, routes
    expected = {(row, selector, slot): 1 for row in range(4) for selector in range(4) for slot in range(SC_WAYS)}

    def sample_phase(phase):
        require_bias_grid(predictions, routes, expected, phase=phase)
        for row, selector, slot in expected:
            coverage.sample({"setup": mode, "phase": phase, "row": row, "bias": selector,
                             "way": (MASKED_POSITIONS[slot] % SC_WAYS) ^ (MASKED_POSITIONS[slot] // SC_WAYS)})

    sample_phase("cold")
    for prediction in predictions.values():
        assert prediction.useds[:SC_WAYS] == (0,) * SC_WAYS, prediction
    cold = predictions
    positive_feedback = tuple(ScBatchTraining(SAME_BANK_PCS[row], cold[row, 0].meta,
        tuple(ScBranchFeedback(position, 1, slot) for slot, position in enumerate(MASKED_POSITIONS)))
        for row in range(4)) * 4
    for attempt in range(16):
        await send_bias_feedback(agent, positive_feedback, adjacent=adjacent)
        predictions = await read_bias_grid(agent)
        require_bias_grid(predictions, routes, expected, phase=("learning", mode, attempt))
        if all(predictions[row, 0].useds[:SC_WAYS] == (1,) * SC_WAYS and
               predictions[row, 0].takens[:SC_WAYS] == (1,) * SC_WAYS for row in range(4)):
            break
    else:
        raise AssertionError(("four-row positive learning did not converge", mode, predictions))
    sample_phase("queued_learned")
    positive = predictions

    # train_batches waits through the update pipeline and four-slot drain;
    # readback is also finished before sending each spaced feedback. The
    # next update addresses already written rows, not newly allocated rows.
    for slot in range(SC_WAYS):
        selected = {(row, 0, slot) for row in range(4)}
        feedback = tuple(ScBatchTraining(SAME_BANK_PCS[row], positive[row, 0].meta,
            (ScBranchFeedback(MASKED_POSITIONS[slot], 0, slot),)) for row in range(4))
        for attempt in range(64):
            await send_bias_feedback(agent, feedback, adjacent=False)
            predictions = await read_bias_grid(agent)
            require_bias_grid(predictions, routes, expected, phase=("rewrite", mode, slot, attempt), mutable=selected)
            if all(predictions[row, 0].meta["debug"]["scBiasTakenVec"][slot] == 0 for row in range(4)):
                expected.update({coordinate: 0 for coordinate in selected})
                break
        else:
            failed_rows = {row: predictions[row, 0] for row in range(4)
                           if predictions[row, 0].meta["debug"]["scBiasTakenVec"][slot] != 0}
            raise AssertionError(("existing bias way did not reverse", mode, {
                "slot": slot, "position": MASKED_POSITIONS[slot], "expected_bias": 0,
                "attempts": 64, "failed_rows": failed_rows,
            }))
        sample_phase(f"negative_slot_{slot}")

    negative = predictions
    assert all(predictions[row, 0].takens[:SC_WAYS] == (0,) * SC_WAYS for row in range(4)), predictions
    selected = {(row, 0, slot) for row in range(4) for slot in range(SC_WAYS) if (row + slot) % 2 == 0}
    feedback = tuple(ScBatchTraining(SAME_BANK_PCS[row], negative[row, 0].meta,
        tuple(ScBranchFeedback(MASKED_POSITIONS[slot], 1, slot) for slot in range(SC_WAYS)
              if (row, 0, slot) in selected)) for row in range(4))
    for attempt in range(64):
        await send_bias_feedback(agent, feedback, adjacent=False)
        predictions = await read_bias_grid(agent)
        require_bias_grid(predictions, routes, expected, phase=("relearn", mode, attempt), mutable=selected)
        if all(predictions[row, 0].meta["debug"]["scBiasTakenVec"][slot] == 1 for row, _, slot in selected):
            expected.update({coordinate: 1 for coordinate in selected})
            break
    else:
        raise AssertionError(("existing bias subset did not relearn", mode, predictions))
    sample_phase("subset_relearned")
    predictions = await read_bias_grid(agent, repeated=True)
    sample_phase("mixed_pipeline")
    return expected


async def check_clean_reactivation(agent, coverage):
    pending = await check_clean_reactivation_mode(agent, coverage, adjacent=True)
    serial = await check_clean_reactivation_mode(agent, coverage, adjacent=False)
    assert pending == serial
