"""Equal upper indices must distinguish independently owned PC/history tags."""

from suites.frontend.bpu.models.configuration import PHR_FOLDS
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.semantic import Context, training_folds
from suites.frontend.bpu.models.folded_history import folded_history_values
from suites.frontend.bpu.utage.checker.assertions import counter
from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.case.definitions import SATURATION_ATTEMPTS
from suites.frontend.bpu.utage.case.shadow_ring_scenario import send_shadow_feedback


COLLISION_PHASES = (
    "trained", "blocked", "first_error_blocked", "freed", "reallocated",
    "b_direction_corrected", "saturated", "late_a", "late_b", "pipelined",
)


def collision_histories(bank, fold_pair):
    a = 256 | bank
    # The nine-bit history-to-index mapping is injective for a fixed PC.
    # An independent PC bit cancels in the row hash but changes the tag.
    b = a ^ (1 << (fold_pair + 5))
    return {"a": a, "b": b, "neighbor": 128 | 8 | bank}


def collision_pc(history):
    return PASSING_PC ^ (history & 0xe0)


def collision_indices(history):
    return (collision_pc(history) ^ (history & 31)) & 511, (collision_pc(history) ^ history) & 511


def require_collision_state(prediction, name, history, base, expected, *, phase):
    entry = prediction.meta["abtbResult"][0]
    state = (phase, name, history, prediction)
    assert prediction.meta["readIndex"] == collision_indices(history), state
    assert training_folds(tuple(row['foldedHist'] for row in
        prediction.meta["foldedPathHistForTrain_hist"])) == training_folds(
            Context.from_recent(history)), state
    assert (entry["valid"], entry["cfiPosition"], entry["baseTaken"]) == (1, POSITION, base), state
    if expected is None:
        assert (prediction.hit, entry["hit"]) == (0, 0), state
    else:
        table, taken_counter = expected
        assert (prediction.hit, entry["hit"], entry["tableId"], counter(prediction), prediction.taken) == (
            1, 1, table, taken_counter, int(taken_counter >= 4),
        ), state
        assert entry["predTaken"] == prediction.taken, state


async def read_collision_grid(agent, histories, expected, *, phase, repeated=False):
    names = ("a", "b", "neighbor")
    if repeated:
        names = ("a", "b", "neighbor", "b", "a", "neighbor") * 4
    bases = {"a": 1, "b": 0, "neighbor": 1}
    transfers = [agent.submit_predict(collision_pc(histories[name]), POSITION, bases[name], folded_history=histories[name])
                 for name in names]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(names), 2)), ticks
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in ticks]
    result = {}
    for name, transfer in zip(names, transfers, strict=True):
        prediction = await transfer
        require_collision_state(prediction, name, histories[name], bases[name], expected[name], phase=phase)
        result[name] = prediction
    return result


async def allocate_weak_upper(agent, history, name):
    cold = await agent.predict(collision_pc(history), POSITION, 0, folded_history=history)
    require_collision_state(cold, name, history, 0, None, phase="prepare.cold")
    await agent.train(UtageTraining(collision_pc(history), POSITION, 1, cold.meta))
    lower = await agent.predict(collision_pc(history), POSITION, 0, folded_history=history)
    require_collision_state(lower, name, history, 0, (0, 4), phase="prepare.lower")
    await agent.train(UtageTraining(collision_pc(history), POSITION, 0, lower.meta))
    upper = await agent.predict(collision_pc(history), POSITION, 1, folded_history=history)
    require_collision_state(upper, name, history, 1, (1, 3), phase="prepare.upper")


async def check_collision_case(agent, coverage, *, bank, fold_pair, adjacent):
    await agent.reset()
    histories = collision_histories(bank, fold_pair)
    indices = {name: collision_indices(history) for name, history in histories.items()}
    assert indices["a"][1] == indices["b"][1] == 256 | bank, indices
    assert len({index[0] for index in indices.values()}) == 3, indices
    assert indices["neighbor"][1] != indices["a"][1], indices
    mode = "adjacent" if adjacent else "serial"

    async def read_phase(phase, expected, *, repeated=False):
        results = await read_collision_grid(agent, histories, expected, phase=phase, repeated=repeated)
        for name in histories:
            coverage.sample({"mode": mode, "bank": bank, "fold_pair": fold_pair,
                             "phase": phase, "context": name})
        return results

    await allocate_weak_upper(agent, histories["a"], "a")
    await allocate_weak_upper(agent, histories["neighbor"], "neighbor")
    cold_b = await agent.predict(collision_pc(histories["b"]), POSITION, 0, folded_history=histories["b"])
    require_collision_state(cold_b, "b", histories["b"], 0, None, phase="prepare.collision_miss")
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 1, cold_b.meta))
    observed = await read_phase("trained", {"a": (1, 3), "b": (0, 4), "neighbor": (1, 3)})

    # Upper A is useful=2: B's real lower-provider error must be blocked.
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 0, observed["b"].meta))
    observed = await read_phase("blocked", {"a": (1, 3), "b": (0, 3), "neighbor": (1, 3)})
    await agent.train(UtageTraining(collision_pc(histories["a"]), POSITION, 1, observed["a"].meta))
    observed = await read_collision_grid(agent, histories,
        {"a": (1, 4), "b": (0, 3), "neighbor": (1, 3)}, phase="first_error")
    # One error leaves useful=1, so B must still not replace A's upper tag.
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 1, observed["b"].meta))
    observed = await read_phase("first_error_blocked", {"a": (1, 4), "b": (0, 4), "neighbor": (1, 3)})
    await agent.train(UtageTraining(collision_pc(histories["a"]), POSITION, 0, observed["a"].meta))
    observed = await read_phase("freed", {"a": (1, 3), "b": (0, 4), "neighbor": (1, 3)})
    captured_a = observed["a"]

    # The second error makes useful zero: same physical upper row now takes
    # B's tag. A must reject it and fall back to its unchanged lower counter.
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 0, observed["b"].meta))
    observed = await read_phase("reallocated", {"a": (0, 3), "b": (1, 3), "neighbor": (1, 3)})
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 1, observed["b"].meta))
    observed = await read_phase("b_direction_corrected", {"a": (0, 3), "b": (1, 4), "neighbor": (1, 3)})
    feedback = tuple(UtageTraining(collision_pc(histories["b"]), POSITION, 1, observed["b"].meta, mispredict=0)
                     for _ in range(SATURATION_ATTEMPTS))
    await send_shadow_feedback(agent, feedback, adjacent=adjacent)
    observed = await read_phase("saturated", {"a": (0, 3), "b": (1, 7), "neighbor": (1, 3)})
    captured_b = observed["b"]

    # Captured, genuinely emitted feedback is allowed to arrive after a
    # different tag occupies this row. The RTL reconstructs from the captured
    # counter, not the other resident tag's counter: A 3+1=4, then B 7-1=6.
    await agent.train(UtageTraining(collision_pc(histories["a"]), POSITION, 1, captured_a.meta))
    await read_phase("late_a", {"a": (1, 4), "b": (0, 3), "neighbor": (1, 3)})
    await agent.train(UtageTraining(collision_pc(histories["b"]), POSITION, 0, captured_b.meta))
    expected = {"a": (0, 3), "b": (1, 6), "neighbor": (1, 3)}
    await read_phase("late_b", expected)
    await read_phase("pipelined", expected, repeated=True)


async def check_history_collisions(agent, coverage):
    for adjacent in (True, False):
        for fold_pair in range(3):
            for bank in range(4):
                await check_collision_case(agent, coverage, bank=bank, fold_pair=fold_pair, adjacent=adjacent)
