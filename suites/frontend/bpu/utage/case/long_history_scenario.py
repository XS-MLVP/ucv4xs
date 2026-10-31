"""Same short-history provider, independent long-history providers."""

from suites.frontend.bpu.models.configuration import PHR_FOLDS
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.semantic import Context, training_folds
from suites.frontend.bpu.models.folded_history import folded_history_values
from suites.frontend.bpu.utage.checker.assertions import counter
from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.case.definitions import SATURATION_ATTEMPTS


def requests_for_bit(older_bit):
    return tuple((bank, name, bank | mask, base) for bank in range(4)
                 for name, mask, base in (("a", 0, 1), ("b", 1 << older_bit, 0),
                                          ("lower_only", 1 << 5, 0)))


def require_long_history(prediction, bank, name, history, base, table, taken_counter):
    entry = prediction.meta["abtbResult"][0]
    upper_index = history & 511
    state = (bank, name, history, prediction)
    assert prediction.meta["readIndex"] == (bank, upper_index), state
    assert training_folds(tuple(row['foldedHist'] for row in
        prediction.meta["foldedPathHistForTrain_hist"])) == training_folds(
            Context.from_recent(history)), state
    assert (entry["valid"], entry["cfiPosition"], entry["baseTaken"]) == (1, POSITION, base), state
    assert (prediction.hit, entry["hit"], entry["tableId"], counter(prediction), prediction.taken) == (
        1, 1, table, taken_counter, int(taken_counter >= 4),
    ), state
    assert entry["predTaken"] == prediction.taken, state


async def read_long_history_grid(agent, requests, expected, *, repetitions=1):
    # Both forward and reverse order put different histories on adjacent A0/A1
    # stages. All transfers are submitted before driver/monitor draining.
    sequence = requests if repetitions == 1 else (requests + requests[::-1]) * repetitions
    transfers = [agent.submit_predict(PASSING_PC, POSITION, base, folded_history=history)
                 for _, _, history, base in sequence]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(sequence), 2)), ticks
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in ticks]
    results = tuple([await transfer for transfer in transfers])
    for request, prediction in zip(sequence, results, strict=True):
        bank, name, history, base = request
        table, taken_counter = expected[bank, name]
        require_long_history(prediction, bank, name, history, base, table, taken_counter)
    return results


def sample_long_history(coverage, requests, older_bit, phase):
    for bank, name, _, _ in requests:
        coverage.sample({"phase": phase, "bank": bank, "older_bit": older_bit, "context": name})


async def check_short_alias_long_history(agent, coverage):
    for older_bit in (6, 7, 8):
        await agent.reset()
        requests = requests_for_bit(older_bit)
        expected = {}
        for bank in range(4):
            cold = await agent.predict(PASSING_PC, POSITION, 0, folded_history=bank)
            assert cold.hit == 0 and cold.meta["readIndex"] == (bank, bank), cold
            await agent.train(UtageTraining(PASSING_PC, POSITION, 1, cold.meta))
            lower = await agent.predict(PASSING_PC, POSITION, 0, folded_history=bank)
            require_long_history(lower, bank, "a.lower", bank, 0, 0, 4)
            await agent.train(UtageTraining(PASSING_PC, POSITION, 0, lower.meta))
            a = await agent.predict(PASSING_PC, POSITION, 1, folded_history=bank)
            require_long_history(a, bank, "a", bank, 1, 1, 3)

            # The older bit lies beyond the five-bit short window: B must
            # inherit A's lower provider, but its nine-bit upper row is cold.
            history_b = bank | (1 << older_bit)
            b = await agent.predict(PASSING_PC, POSITION, 1, folded_history=history_b)
            require_long_history(b, bank, "b.lower", history_b, 1, 0, 3)
            await agent.train(UtageTraining(PASSING_PC, POSITION, 1, b.meta))
            b = await agent.predict(PASSING_PC, POSITION, 0, folded_history=history_b)
            require_long_history(b, bank, "b", history_b, 0, 1, 4)
            expected.update({(bank, "a"): (1, 3), (bank, "b"): (1, 4),
                             (bank, "lower_only"): (0, 4)})
        await read_long_history_grid(agent, requests, expected)
        sample_long_history(coverage, requests, older_bit, "trained")

        for name, actual, base, final_counter in (("a", 0, 1, 0), ("b", 1, 0, 7)):
            for bank in range(4):
                history = bank | (0 if name == "a" else 1 << older_bit)
                current = await agent.predict(PASSING_PC, POSITION, base, folded_history=history)
                table, old_counter = expected[bank, name]
                require_long_history(current, bank, name, history, base, table, old_counter)
                await agent.train_many(tuple(UtageTraining(
                    PASSING_PC, POSITION, actual, current.meta, mispredict=0,
                ) for _ in range(SATURATION_ATTEMPTS)))
                expected[bank, name] = (1, final_counter)
                # Every update must leave all other banks, the opposite upper
                # history and the shared lower-only fallback unchanged.
                await read_long_history_grid(agent, requests, expected)
            sample_long_history(coverage, requests, older_bit, name + "_saturated")
        await read_long_history_grid(agent, requests, expected, repetitions=2)
        sample_long_history(coverage, requests, older_bit, "mixed_pipeline")
