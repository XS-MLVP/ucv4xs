"""Observable allocation probes distinguish decrement from shift aging."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from bpuverify.utage.transaction.types import UtagePrediction
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.checker.assertions import counter
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@dataclass(frozen=True)
class AgingContext:
    pc: int
    history: int
    bank: int
    strength: int
    initial: UtagePrediction
    position: int = POSITION


async def prepare_aging_context(agent, *, pc, history, bank, strength):
    cold = await agent.predict(pc, POSITION, 0, folded_history=history)
    assert cold.hit == 0, cold
    await agent.train(UtageTraining(pc, POSITION, 1, cold.meta))
    lower = await agent.predict(pc, POSITION, 0, folded_history=history)
    assert (lower.hit, lower.taken, counter(lower), lower.meta["abtbResult"][0]["tableId"]) == (1, 1, 4, 0), lower
    await agent.train(UtageTraining(pc, POSITION, 1, lower.meta, mispredict=0))
    saved_lower = await agent.predict(pc, POSITION, 0, folded_history=history)
    assert (saved_lower.hit, saved_lower.taken, counter(saved_lower)) == (1, 1, 5), saved_lower

    # Lower useful: allocation 1 -> correct 2 -> error 1. Genuine older
    # lower-provider metadata can reinforce it to 2/3 without changing upper.
    await agent.train(UtageTraining(pc, POSITION, 0, saved_lower.meta))
    for _ in range(strength - 1):
        await agent.train(UtageTraining(pc, POSITION, 1, saved_lower.meta, mispredict=0))
    upper = await agent.predict(pc, POSITION, 1, folded_history=history)
    assert (upper.hit, upper.taken, counter(upper), upper.meta["abtbResult"][0]["tableId"]) == (1, 0, 3, 1), upper
    # Upper useful starts at 2; one correct correction of a taken base makes
    # it 3. Its counter becomes 2 and must stay 2 throughout global aging.
    await agent.train(UtageTraining(pc, POSITION, 0, upper.meta, mispredict=0))
    upper = await agent.predict(pc, POSITION, 1, folded_history=history)
    assert (upper.hit, upper.taken, counter(upper), upper.meta["abtbResult"][0]["tableId"]) == (1, 0, 2, 1), upper
    assert all(index & 3 == bank for index in upper.meta["readIndex"]), upper
    return AgingContext(pc, history, bank, strength, upper)


async def read_aging_matrix(agent, contexts, *, position, base_taken):
    transfers = [agent.submit_predict(context.pc, position, base_taken,
                                      folded_history=context.history) for context in contexts]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(contexts), 2)), ticks
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in ticks]
    return tuple([await transfer for transfer in transfers])


def require_aging_matrix(contexts, predictions, expected, *, position, base_taken, phase):
    for context, prediction in zip(contexts, predictions, strict=True):
        entry = prediction.meta["abtbResult"][0]
        state = (phase, context.bank, context.strength, prediction)
        assert entry["valid"] == 1 and entry["cfiPosition"] == position, state
        assert entry["baseTaken"] == base_taken, state
        assert prediction.meta["readIndex"] == context.initial.meta["readIndex"], state
        assert prediction.meta["foldedPathHistForTrain_hist"] == context.initial.meta["foldedPathHistForTrain_hist"], state
        wanted = expected[context.bank, context.strength]
        if wanted is None:
            # takenVec is a table read's raw direction even on a position
            # miss. BPU uses it only when hitVec is set; miss training uses
            # the asserted baseTaken metadata, not that invalid raw direction.
            assert (prediction.hit, entry["hit"]) == (0, 0), state
        else:
            table, taken_counter = wanted
            assert (prediction.hit, entry["hit"], entry["tableId"], counter(prediction), prediction.taken) == (
                1, 1, table, taken_counter, int(taken_counter >= 4),
            ), state
            assert entry["predTaken"] == prediction.taken, state


async def check_aging_matrices(agent, contexts, aliases, originals, *, phase):
    alias_readback = await read_aging_matrix(agent, contexts, position=POSITION + 1, base_taken=0)
    require_aging_matrix(contexts, alias_readback, aliases,
                         position=POSITION + 1, base_taken=0, phase=phase + ".alias")
    original_readback = await read_aging_matrix(agent, contexts, position=POSITION, base_taken=1)
    require_aging_matrix(contexts, original_readback, originals,
                         position=POSITION, base_taken=1, phase=phase + ".original")
    return alias_readback


async def failed_provider_feedback(agent, source, count):
    """Each fresh highest-table error is exactly one failed allocation."""

    previous = await agent.predict(source.pc, source.position, 1, folded_history=source.history)
    assert previous.hit == 1 and previous.meta["abtbResult"][0]["tableId"] == 1, previous
    for attempt in range(count):
        actual = 1 - previous.taken
        expected_counter = min(7, counter(previous) + 1) if actual else max(0, counter(previous) - 1)
        await agent.train(UtageTraining(source.pc, source.position, actual, previous.meta))
        observed = await agent.predict(source.pc, source.position, 1, folded_history=source.history)
        assert (observed.hit, observed.meta["abtbResult"][0]["tableId"], counter(observed)) == (
            1, 1, expected_counter,
        ), (attempt, previous, observed)
        assert observed.meta["readIndex"] == source.initial.meta["readIndex"], observed
        previous = observed


async def prepare_aging_source(agent):
    source = await prepare_aging_context(agent, pc=PASSING_PC + 0x40,
                                         history=12, bank=0, strength=1)
    # Prove the useful increment, rather than assuming that a correct taken
    # counter implies correct useful: two errors leave 3 -> 2 -> 1 blocked;
    # the third makes useful zero and opens only the upper table.
    await failed_provider_feedback(agent, source, 2)
    cold = await agent.predict(source.pc, POSITION + 1, 0, folded_history=source.history)
    assert cold.hit == 0, cold
    await agent.train(UtageTraining(source.pc, POSITION + 1, 1, cold.meta))
    blocked = await agent.predict(source.pc, POSITION + 1, 0, folded_history=source.history)
    assert blocked.hit == 0, ("upper useful must still be positive after two errors", blocked)
    await failed_provider_feedback(agent, source, 1)
    cold = await agent.predict(source.pc, POSITION + 1, 0, folded_history=source.history)
    await agent.train(UtageTraining(source.pc, POSITION + 1, 1, cold.meta))
    reopened = await agent.predict(source.pc, POSITION + 1, 0, folded_history=source.history)
    assert (reopened.hit, reopened.taken, reopened.meta["abtbResult"][0]["tableId"], counter(reopened)) == (
        1, 1, 1, 4,
    ), ("third error must reopen only upper", reopened)
    await agent.train(UtageTraining(source.pc, POSITION + 1, 1, reopened.meta, mispredict=0))
    strengthened = await agent.predict(source.pc, POSITION + 1, 0, folded_history=source.history)
    assert (strengthened.hit, strengthened.meta["abtbResult"][0]["tableId"], counter(strengthened)) == (1, 1, 5), strengthened
    preserved = await agent.predict(source.pc, POSITION, 1, folded_history=source.history)
    assert (preserved.hit, preserved.meta["abtbResult"][0]["tableId"], counter(preserved)) == (1, 0, 4), preserved
    # Three highest-provider errors plus one blocked alias counted four
    # failures; the successful upper allocation and correct feedback do not.
    return replace(source, initial=strengthened, position=POSITION + 1), 4


def sample_aging_phase(coverage, contexts, phase):
    for context in contexts:
        coverage.sample({"phase": phase, "bank": context.bank, "strength": context.strength})


async def check_two_round_aging(agent, coverage):
    await agent.reset()
    source, preparation_failures = await prepare_aging_source(agent)
    contexts = []
    for bank in range(4):
        for strength, pc, offset in ((1, PASSING_PC, 0), (2, PASSING_PC + 0x40, 0), (3, PASSING_PC, 8)):
            contexts.append(await prepare_aging_context(
                agent, pc=pc, history=bank + offset, bank=bank, strength=strength,
            ))
    contexts = tuple(contexts)
    for table in range(2):
        indices = {context.initial.meta["readIndex"][table] for context in contexts}
        assert len(indices) == 12 and source.initial.meta["readIndex"][table] not in indices
    aliases = {(context.bank, context.strength): None for context in contexts}
    originals = {(context.bank, context.strength): (1, 2) for context in contexts}

    # All twelve cold aliases are blocked by both tables' nonzero useful.
    # Those twelve genuine misses contribute twelve to the 128-failure tick.
    for context in contexts:
        cold = await agent.predict(context.pc, POSITION + 1, 0, folded_history=context.history)
        assert cold.hit == 0 and cold.meta["readIndex"] == context.initial.meta["readIndex"], cold
        await agent.train(UtageTraining(context.pc, POSITION + 1, 1, cold.meta))
        await check_aging_matrices(agent, contexts, aliases, originals, phase="initial_blocked")
    sample_aging_phase(coverage, contexts, "initial_blocked")

    await failed_provider_feedback(agent, source, 128 - len(contexts) - preparation_failures)
    for context in contexts:
        cold = await agent.predict(context.pc, POSITION + 1, 0, folded_history=context.history)
        assert cold.hit == 0, cold
        await agent.train(UtageTraining(context.pc, POSITION + 1, 1, cold.meta))
        if context.strength == 1:
            aliases[context.bank, context.strength] = (0, 4)
        await check_aging_matrices(agent, contexts, aliases, originals, phase="first_age_allocation")
    sample_aging_phase(coverage, contexts, "first_age_allocation")

    # Upper 3 >> 1 remains 1, so a lower-provider error still cannot escalate.
    # Eight blocked cold aliases above plus these four errors add twelve
    # failed allocations before the second 128-failure tick.
    for context in contexts:
        if context.strength != 1:
            continue
        lower = await agent.predict(context.pc, POSITION + 1, 0, folded_history=context.history)
        assert lower.hit == lower.taken == 1 and counter(lower) == 4, lower
        await agent.train(UtageTraining(context.pc, POSITION + 1, 0, lower.meta))
        aliases[context.bank, context.strength] = (0, 3)
        await check_aging_matrices(agent, contexts, aliases, originals, phase="first_age_upper_blocked")
    sample_aging_phase(coverage, contexts, "first_age_upper_blocked")

    await failed_provider_feedback(agent, source, 128 - len(contexts))
    for context in contexts:
        current = await agent.predict(context.pc, POSITION + 1, 0, folded_history=context.history)
        await agent.train(UtageTraining(context.pc, POSITION + 1, 1, current.meta))
        if context.strength == 2:
            # Lower 2 -> 1 -> 0 reopens first; upper 3 -> 1 -> 0 then also
            # permits real lower-provider-error allocation at the same index.
            aliases[context.bank, context.strength] = (0, 4)
            await check_aging_matrices(agent, contexts, aliases, originals, phase="second_age_lower_first")
            lower = await agent.predict(context.pc, POSITION + 1, 0, folded_history=context.history)
            await agent.train(UtageTraining(context.pc, POSITION + 1, 0, lower.meta))
            aliases[context.bank, context.strength] = (1, 3)
        else:
            aliases[context.bank, context.strength] = (1, 4)
        # Strength 3 is still useful in lower (3 -> 2 -> 1), so the miss
        # allocates upper directly and leaves the old lower provider intact.
        originals[context.bank, context.strength] = (0, 6) if context.strength == 3 else None
        await check_aging_matrices(agent, contexts, aliases, originals, phase="second_age_allocation")
    sample_aging_phase(coverage, contexts, "second_age_allocation")
    await check_aging_matrices(agent, contexts, aliases, originals, phase="final_original_preserved")
    sample_aging_phase(coverage, contexts, "final_original_preserved")
