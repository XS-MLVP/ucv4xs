from __future__ import annotations
from bpuverify.common.model.configuration import *

from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.transaction.types import ScTraining
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.sc.case.definitions import TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import BIAS_COUNTERS
from bpuverify.sc.case.definitions import MASKED_OUTCOMES
from bpuverify.sc.case.definitions import MASKED_POSITIONS
from bpuverify.sc.case.definitions import SAME_BANK_PCS


def require_used(prediction) -> None:
    assert prediction.used == 1, prediction


async def learn(agent, direction: int, *, pc: int = PC, position: int = POSITION):
    prediction = await agent.predict(pc, position, TAGE_COUNTER)
    attempts = TAKEN_ATTEMPTS if direction else NOT_TAKEN_ATTEMPTS
    for _ in range(attempts):
        await agent.train(ScTraining(pc, position, direction, prediction.meta))
        prediction = await agent.predict(pc, position, TAGE_COUNTER)
        if prediction.used and prediction.taken == direction:
            return prediction
    raise AssertionError(
        f"SC failed to learn direction={direction}: prediction={prediction!r}"
    )


async def learn_interleaved_rows(agent, contexts, *, adjacent: bool, limit: int):
    """Check bounded learning with pending writes, not serial-equivalent speed."""

    await agent.reset()
    predictions = [
        await agent.predict(pc, position, TAGE_COUNTER)
        for pc, position, _ in contexts
    ]
    cold = tuple(predictions)
    for rounds in range(1, limit + 1):
        feedback = tuple(
            ScBatchTraining(pc, prediction.meta, (
                ScBranchFeedback(position, outcome, prediction_slot=0),
            ))
            for (pc, position, outcome), prediction in zip(contexts, predictions)
        ) * 4
        # Adjacent training reads keep the bank busy. Four indices can coexist
        # in the four pending slots without relying on full-miss replacement.
        if adjacent:
            await agent.train_batches(feedback)
        else:
            for transaction in feedback:
                await agent.train_batch(transaction)
        predictions = [
            await agent.predict(pc, position, TAGE_COUNTER)
            for pc, position, _ in contexts
        ]
        if all(
            prediction.used == 1 and prediction.taken == outcome
            for (_, _, outcome), prediction in zip(contexts, predictions)
        ):
            return rounds, cold, tuple(predictions)
    raise AssertionError(
        f"SC interleaved rows failed to converge ({adjacent=}, {limit=}): "
        f"{contexts=}, {predictions=}"
    )


def sc_row_indices(prediction):
    debug = prediction.meta["debug"]
    return (
        debug["predBiasIdx"], debug["predImliIdx"],
        *debug["predPathIdx"], *debug["predGlobalIdx"], *debug["predBWIdx"],
    )


async def learn_masked_rows(agent, *, adjacent: bool, limits):
    """Train one branch way, preserving learned and untouched neighbor ways."""

    await agent.reset()
    layouts = tuple(
        tuple(ScBaseBranch(position, counter) for position in MASKED_POSITIONS)
        for counter in BIAS_COUNTERS
    )

    async def read_rows():
        transfers = [
            agent.submit_predict_branches(pc, layout)
            for pc, layout in zip(SAME_BANK_PCS, layouts, strict=True)
        ]
        await agent.drain_predictions()
        return tuple([await transfer for transfer in transfers])

    predictions = await read_rows()
    cold = predictions
    routes = tuple(map(sc_row_indices, cold))
    for table_rows in zip(*routes):
        assert len(set(table_rows)) == 4, routes
    for selector, (prediction, counter) in enumerate(zip(cold, BIAS_COUNTERS)):
        assert prediction.useds[:SC_WAYS] == (0,) * SC_WAYS, prediction
        # SC takens are the raw correction, not the TAGE fallback when unused.
        assert prediction.takens[:SC_WAYS] == (1,) * SC_WAYS, prediction
        assert prediction.meta["tagePredValid"][:SC_WAYS] == (1,) * SC_WAYS, prediction
        assert prediction.meta["tageCtr"][:SC_WAYS] == (counter,) * SC_WAYS, prediction
        assert prediction.meta["scBiasLowerBits"][:SC_WAYS] == (selector,) * SC_WAYS, prediction

    stages, convergence = [], []
    for slot, (outcome, limit) in enumerate(zip(MASKED_OUTCOMES, limits, strict=True)):
        for rounds in range(1, limit + 1):
            feedback = tuple(
                ScBatchTraining(pc, prediction.meta, (
                    ScBranchFeedback(MASKED_POSITIONS[slot], outcome, prediction_slot=slot),
                ))
                for pc, prediction in zip(SAME_BANK_PCS, predictions, strict=True)
            ) * 4
            if adjacent:
                await agent.train_batches(feedback)
            else:
                for transaction in feedback:
                    await agent.train_batch(transaction)
            predictions = await read_rows()
            for row, prediction in enumerate(predictions):
                assert sc_row_indices(prediction) == routes[row], prediction
                assert prediction.meta["tagePredValid"][:SC_WAYS] == (1,) * SC_WAYS, prediction
                assert prediction.meta["scBiasLowerBits"][:SC_WAYS] == (row,) * SC_WAYS, prediction
                for other in range(SC_WAYS):
                    if other == slot:
                        continue
                    wanted_used = int(other < slot)
                    wanted_taken = MASKED_OUTCOMES[other] if other < slot else 1
                    assert (prediction.useds[other], prediction.takens[other]) == (
                        wanted_used, wanted_taken,
                    ), (adjacent, slot, rounds, row, other, prediction)
                    assert prediction.meta["scPred"][other] == wanted_taken, prediction
                    assert prediction.meta["useScPred"][other] == wanted_used, prediction
            if all(
                prediction.useds[slot] == 1 and prediction.takens[slot] == outcome
                for prediction in predictions
            ):
                stages.append(predictions)
                convergence.append(rounds)
                break
        else:
            raise AssertionError(
                f"SC masked pending feedback failed: {adjacent=}, {slot=}, "
                f"{limit=}, {predictions=}"
            )
    return cold, tuple(stages), tuple(convergence)
