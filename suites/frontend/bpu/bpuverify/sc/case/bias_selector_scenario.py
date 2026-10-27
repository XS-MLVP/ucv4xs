"""Selector masks inside one bias row must preserve all other selectors."""
from bpuverify.common.model.configuration import *

from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.checker.assertions import sc_row_indices
from bpuverify.sc.case.definitions import BIAS_COUNTERS
from bpuverify.sc.case.definitions import MASKED_POSITIONS
from bpuverify.sc.case.definitions import SAME_BANK_PCS


async def read_bias_grid(agent, *, repeated=False):
    coordinates = [(row, selector) for selector in range(4) for row in range(4)]
    if repeated:
        coordinates += list(reversed(coordinates))
    transfers = [agent.submit_predict_branches(
        SAME_BANK_PCS[row],
        tuple(ScBaseBranch(position, BIAS_COUNTERS[selector]) for position in MASKED_POSITIONS),
    ) for row, selector in coordinates]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(ticks), 2)), ticks
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 2 for tick in ticks]
    predictions = {}
    for coordinate, transfer in zip(coordinates, transfers, strict=True):
        prediction = await transfer
        if coordinate in predictions:
            assert prediction == predictions[coordinate], (coordinate, prediction, predictions[coordinate])
        predictions[coordinate] = prediction
    return predictions


def require_bias_grid(predictions, routes, expected, *, phase, mutable=()):
    """Bias debug predictions isolate this family from the shared total sum."""
    for (row, selector), prediction in predictions.items():
        state = (phase, row, selector, prediction)
        assert prediction.meta["tagePredValid"][SC_WAYS:] == (0,) * (RESULT_SLOTS - SC_WAYS), state
        assert sc_row_indices(prediction) == routes[row], state
        assert prediction.meta["tagePredValid"][:SC_WAYS] == (1,) * SC_WAYS, state
        assert prediction.meta["tageCtr"][:SC_WAYS] == (BIAS_COUNTERS[selector],) * SC_WAYS, state
        assert prediction.meta["scBiasLowerBits"][:SC_WAYS] == (selector,) * SC_WAYS, state
        assert prediction.meta["scPred"] == prediction.takens, state
        assert prediction.meta["useScPred"] == prediction.useds, state
        actual = prediction.meta["debug"]["scBiasTakenVec"]
        for slot in range(SC_WAYS):
            if (row, selector, slot) not in mutable:
                assert actual[slot] == expected[row, selector, slot], (state, slot, expected[row, selector, slot])


async def send_bias_feedback(agent, feedback, *, adjacent):
    first = len(agent.training_observations)
    if adjacent:
        await agent.train_batches(feedback)
    else:
        for transaction in feedback:
            await agent.train_batch(transaction)
    observed = agent.training_observations[first:]
    assert len(observed) == len(feedback), ("feedback beat count", len(observed), len(feedback))
    for observation, transaction in zip(observed, feedback, strict=True):
        sample = observation.value
        assert sample.pc.as_int() == transaction.pc, (observation, transaction)
        assert tuple(x.as_int() for x in sample.selectors) == transaction.meta["scBiasLowerBits"], (
            "feedback selectors", observation, transaction,
        )
        active = tuple((b.position.as_int(), b.taken.as_int(), b.branch_type.as_int())
                       for b in sample.branches if b.valid.as_int())
        assert active == tuple((b.position, b.actual_taken, b.branch_type)
                               for b in transaction.branches if b is not None), (active, transaction)
    ticks = [observation.event.tick for observation in observed]
    spacings = [b - a for a, b in zip(ticks, ticks[1:])]
    assert all(spacing == 2 if adjacent else spacing > 2 for spacing in spacings), (
        "feedback cadence", adjacent, ticks,
    )


async def check_bias_selector_mode(agent, coverage, *, adjacent):
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
            coverage.sample({"mode": mode, "phase": phase, "row": row, "bias": selector,
                             "way": (MASKED_POSITIONS[slot] % SC_WAYS) ^ (MASKED_POSITIONS[slot] // SC_WAYS)})

    sample_phase("cold")
    for prediction in predictions.values():
        assert prediction.useds[:SC_WAYS] == (0,) * SC_WAYS, prediction
        assert prediction.meta["sumAboveThres"][:SC_WAYS] == (0,) * SC_WAYS, prediction
    # Keep genuine cold metadata. Later feedback is still eligible even when
    # other selectors have made the shared non-bias sum confidently negative.
    # This checks delayed feedback, not an artificially edited training gate.
    cold = predictions
    for selector in range(4):
        feedback = tuple(ScBatchTraining(SAME_BANK_PCS[row], cold[row, selector].meta,
            tuple(ScBranchFeedback(position, 0, slot) for slot, position in enumerate(MASKED_POSITIONS)))
            for row in range(4)) * 4
        await send_bias_feedback(agent, feedback, adjacent=adjacent)
        predictions = await read_bias_grid(agent)
        expected.update({(row, selector, slot): 0 for row in range(4) for slot in range(SC_WAYS)})
        sample_phase(f"negative_{selector}")

    # At this point each of the sixteen bias ways in each SRAM row is negative.
    # Correct only a checkerboard of ways; retain the other half and every
    # other selector. Capture this negative prediction before any reversal.
    negative = predictions
    for prediction in negative.values():
        assert prediction.takens[:SC_WAYS] == (0,) * SC_WAYS, prediction
    for selector in range(4):
        selected = {(row, selector, slot) for row in range(4) for slot in range(SC_WAYS)
                    if (row + selector + slot) % 2 == 0}
        feedback = tuple(ScBatchTraining(SAME_BANK_PCS[row], negative[row, selector].meta,
            tuple(ScBranchFeedback(MASKED_POSITIONS[slot], 1, slot) for slot in range(SC_WAYS)
                  if (row, selector, slot) in selected)) for row in range(4)) * 4
        for attempt in range(8):
            await send_bias_feedback(agent, feedback, adjacent=adjacent)
            predictions = await read_bias_grid(agent)
            require_bias_grid(predictions, routes, expected, phase=("reversal", selector, attempt), mutable=selected)
            if all(predictions[row, bias].meta["debug"]["scBiasTakenVec"][slot] == 1
                   for row, bias, slot in selected):
                expected.update({coordinate: 1 for coordinate in selected})
                break
        else:
            raise AssertionError(("bias selector reversal did not converge", mode, selector, predictions))
        sample_phase(f"positive_{selector}")
    predictions = await read_bias_grid(agent, repeated=True)
    sample_phase("mixed_pipeline")
    return expected


async def check_bias_selector_merge(agent, coverage):
    adjacent = await check_bias_selector_mode(agent, coverage, adjacent=True)
    serial = await check_bias_selector_mode(agent, coverage, adjacent=False)
    assert serial == adjacent
