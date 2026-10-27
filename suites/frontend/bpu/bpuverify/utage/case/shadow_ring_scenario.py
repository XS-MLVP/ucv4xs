"""Public-transaction checks for recent-update bypass and shadow-ring eviction."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.utage.transaction.types import UtagePrediction
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.checker.assertions import counter
from bpuverify.utage.case.definitions import POSITION
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.case.definitions import SHADOW_PCS
from bpuverify.utage.case.definitions import SHADOW_REPEAT_BEATS


@dataclass(frozen=True)
class ShadowContext:
    pc: int
    history: int
    prediction: UtagePrediction


@dataclass(frozen=True)
class ShadowRun:
    contexts: tuple[ShadowContext, ...]
    stages: tuple


class LostShadowWriteback(AssertionError):
    """A proven saturated provider loses its counter after shadow replacement."""


async def prepare_shadow_contexts(agent, *, table, bank):
    contexts = []
    for row in range(SHADOW_CAPACITY):
        pc = SHADOW_PCS[row // 4]
        history = bank + 4 * (row % 4)
        cold = await agent.predict(pc, POSITION, 0, folded_history=history)
        assert cold.hit == 0, (table, bank, row, cold)
        await agent.train(UtageTraining(pc, POSITION, 1, cold.meta))
        prediction = await agent.predict(pc, POSITION, 0, folded_history=history)
        assert (prediction.hit, prediction.taken, counter(prediction)) == (1, 1, 4), prediction
        assert prediction.meta["abtbResult"][0]["tableId"] == 0, prediction
        if table == 1:
            # A real lower-provider error allocates the higher table; its
            # weak-negative provider then trains correctly in every burst.
            await agent.train(UtageTraining(pc, POSITION, 0, prediction.meta))
            prediction = await agent.predict(pc, POSITION, 1, folded_history=history)
        assert (prediction.hit, prediction.taken, counter(prediction)) == (
            1, 1 - table, 3 if table else 4,
        ), (table, bank, row, prediction)
        assert prediction.meta["abtbResult"][0]["tableId"] == table, prediction
        assert all(index & 3 == bank for index in prediction.meta["readIndex"]), prediction
        contexts.append(ShadowContext(pc, history, prediction))
    assert all(len({context.prediction.meta["readIndex"][table_id] for context in contexts}) == SHADOW_CAPACITY
               for table_id in range(2))
    return tuple(contexts)


async def read_shadow_contexts(agent, contexts, *, table):
    transfers = [agent.submit_predict(
        context.pc, POSITION, table, folded_history=context.history,
    ) for context in contexts]
    await agent.drain_predictions()
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(contexts), 2))
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in accepted]
    return tuple([await transfer for transfer in transfers])


def shadow_states(contexts, predictions, *, table, phase):
    states = []
    for row, (context, prediction) in enumerate(zip(contexts, predictions, strict=True)):
        entry = prediction.meta["abtbResult"][0]
        state = (table, context.history & 3, row, phase, prediction)
        assert prediction.hit == 1, state
        assert prediction.taken == int(counter(prediction) >= 4), state
        assert (entry["valid"], entry["hit"], entry["tableId"], entry["cfiPosition"], entry["baseTaken"]) == (
            1, 1, table, POSITION, table,
        ), state
        assert prediction.meta["readIndex"] == context.prediction.meta["readIndex"], state
        assert prediction.meta["foldedPathHistForTrain_hist"] == context.prediction.meta["foldedPathHistForTrain_hist"], state
        states.append((prediction.meta["readIndex"], entry["tableId"], prediction.hit, prediction.taken, counter(prediction)))
    return tuple(states)


def require_shadow_state(contexts, predictions, *, table, counters, phase):
    states = shadow_states(contexts, predictions, table=table, phase=phase)
    for row, (state, expected_counter) in enumerate(zip(states, counters, strict=True)):
        assert state[-1] == expected_counter, (table, row, phase, expected_counter, predictions[row])
    return states


async def send_shadow_feedback(agent, transactions, *, adjacent):
    first = len(agent.training_observations)
    if adjacent:
        await agent.train_many(transactions)
    else:
        for transaction in transactions:
            await agent.train(transaction)
    observed = agent.training_observations[first:]
    assert len(observed) == len(transactions), (
        "feedback beat count", adjacent, len(transactions), len(observed),
        [(item.event.tick, item.value.pc.as_int(),
          tuple(index.as_int() for index in item.value.read_index)) for item in observed],
    )
    for observation, transaction in zip(observed, transactions, strict=True):
        assert observation.value.pc.as_int() == transaction.pc
        assert tuple(index.as_int() for index in observation.value.read_index) == tuple(transaction.meta["readIndex"])
    ticks = [observation.event.tick for observation in observed]
    spacings = [following - previous for previous, following in zip(ticks, ticks[1:])]
    if adjacent:
        assert all(spacing == 2 for spacing in spacings), ("feedback is not adjacent", ticks)
    else:
        assert all(spacing > 2 for spacing in spacings), ("feedback is not serial", ticks)


async def check_shadow_ring_mode(agent, coverage, *, table, bank, adjacent):
    mode = "adjacent" if adjacent else "serial"
    await agent.reset()
    contexts = await prepare_shadow_contexts(agent, table=table, bank=bank)
    feedback = tuple(UtageTraining(
        context.pc, POSITION, 1 - table, context.prediction.meta, mispredict=0,
    ) for context in contexts)
    initial_counter, saturated_counter = (3, 0) if table else (4, 7)
    stages = []
    for phase in ("resident", "same_index_bypass", "ring_wrapped"):
        if phase == "same_index_bypass":
            # More than one ring capacity of immediate repeated writes must
            # use the newest entry, not repeatedly reuse the old meta counter.
            await send_shadow_feedback(agent, (feedback[0],) * SHADOW_REPEAT_BEATS, adjacent=adjacent)
        elif phase == "ring_wrapped":
            # Eight independent indices circle through the ring repeatedly.
            # The table can force writeback near full even on a read conflict.
            await send_shadow_feedback(agent, feedback * SHADOW_CAPACITY, adjacent=adjacent)
        predictions = await read_shadow_contexts(agent, contexts, table=table)
        counters = (initial_counter,) * SHADOW_CAPACITY
        if phase == "same_index_bypass":
            counters = (saturated_counter,) + counters[1:]
        elif phase == "ring_wrapped":
            counters = (saturated_counter,) * SHADOW_CAPACITY
        stages.append(require_shadow_state(contexts, predictions, table=table, counters=counters, phase=phase))
        for row in range(SHADOW_CAPACITY):
            coverage.sample({"mode": mode, "table": table, "bank": bank, "phase": phase, "row": row})
    return ShadowRun(contexts, tuple(stages))


async def check_shadow_eviction(agent, coverage, run, *, table, bank, adjacent):
    """Keep all structural prerequisites hard failures; collect counter loss only.

    The caller checks the complete mode/table/bank matrix before classifying a
    known persistence defect, so one failure cannot hide untested contexts.
    """

    mode = "adjacent" if adjacent else "serial"
    initial_counter, saturated_counter = (3, 0) if table else (4, 7)
    before = await read_shadow_contexts(agent, run.contexts, table=table)
    require_shadow_state(run.contexts, before, table=table,
                         counters=(saturated_counter,) * SHADOW_CAPACITY, phase="before_shadow_eviction")
    for row in range(SHADOW_CAPACITY):
        coverage.sample({"mode": mode, "table": table, "bank": bank,
                         "phase": "before_shadow_eviction", "row": row})

    # Eight new indices replace every selected table's shadow slot without
    # replacing the original SRAM rows. No further old-row feedback is sent.
    neighbors = await prepare_shadow_contexts(agent, table=table, bank=bank ^ 1)
    for context, neighbor in zip(run.contexts, neighbors, strict=True):
        assert all(old ^ 1 == new for old, new in zip(
            context.prediction.meta["readIndex"], neighbor.prediction.meta["readIndex"], strict=True,
        ))
    neighbor_readback = await read_shadow_contexts(agent, neighbors, table=table)
    require_shadow_state(neighbors, neighbor_readback, table=table,
                         counters=(initial_counter,) * SHADOW_CAPACITY, phase="neighbor_retained")
    for row in range(SHADOW_CAPACITY):
        coverage.sample({"mode": mode, "table": table, "bank": bank,
                         "phase": "neighbor_retained", "row": row})

    # The declared persistence defect loses the last update of the replaced
    # cells.  Allow only a strict counter loss at exactly those logical cells;
    # hit/tag/position differences and every other cell still fail normally.
    # The collector below remains the authority on which cells were lost.
    for context in run.contexts:
        agent.allow_known_counter_difference(table, context.prediction.meta["readIndex"][table],
                                       'BPU-UTAGE-016 ring slot clears newly enqueued dirty entry')
    after = await read_shadow_contexts(agent, run.contexts, table=table)
    states = shadow_states(run.contexts, after, table=table, phase="after_shadow_eviction")
    mismatches = []
    for row, (context, state) in enumerate(zip(run.contexts, states, strict=True)):
        if state[-1] == saturated_counter:
            coverage.sample({"mode": mode, "table": table, "bank": bank,
                             "phase": "after_shadow_eviction", "row": row})
        else:
            mismatches.append({
                "mode": mode, "table": table, "bank": bank, "row": row,
                "pc_addr": hex(context.pc), "folded_history": context.history,
                "read_index": state[0], "expected_counter": saturated_counter,
                "actual_counter": state[-1], "hit": state[2], "taken": state[3],
                "meta": after[row].meta,
            })
    return states, mismatches
