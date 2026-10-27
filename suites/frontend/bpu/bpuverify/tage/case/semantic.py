"""Distinguishing histories at one PC, not a bank/set sweep."""
from bpuverify.tage.model.semantic import Context
from bpuverify.tage.transaction.types import TageTraining


PC, POSITION = 0x40000000, 6
# Distinct short folds plus nonzero long-history contributions. Their owned
# row/tag coordinates differ in every table; direction alternates to make a
# pipeline context swap observable rather than merely different metadata.
PROFILES = ((0, 0), (1, 1), (0x41234555, 0), (0x23456aaa, 1))


async def predict(agent, history, direction):
    return await agent.predict(PC, POSITION, 1 - direction, history=history)


async def accepted_learning(agent, history, direction, source, coverage, *, allocate):
    before = agent.reference.input_tick
    try:
        await agent.train(TageTraining(PC, POSITION, direction, 1 - direction, source.meta,
                                      mispredict=int(allocate), history=history))
    finally:
        accepted = [(tick, request) for tick, request in agent.reference.accepted_feedback if tick > before]
        if len(accepted) == 1:
            tick, request = accepted[0]
            qualified = (request.pc == PC and request.context == Context.from_recent(history)
                and len(request.branches) == 1 and request.branches[0].position == POSITION
                and request.branches[0].kind == 1 and request.branches[0].matched
                and request.branches[0].taken == bool(direction) and request.branches[0].mispredict == allocate)
            if qualified:
                coverage.record('reached', 'context-allocation' if allocate else 'context-local-learning',
                                accepted_tick=tick, history=history)
    assert len(accepted) == 1
    tick, request = accepted[0]
    assert (request.pc, request.context) == (PC, Context.from_recent(history))
    assert len(request.branches) == 1
    branch = request.branches[0]
    assert (branch.position, branch.taken, branch.kind, branch.matched, branch.mispredict) == (
        POSITION, bool(direction), 1, True, allocate)
    return tick


async def pipelined_readback(agent, coverage):
    profiles = (*PROFILES, *reversed(PROFILES))
    transfers = [agent.submit_predict(PC, POSITION, 1 - direction, history=history)
                 for history, direction in profiles]
    ticks = ()
    try:
        await agent.drain_predictions()
        predictions = [await transfer for transfer in transfers]
    finally:
        accepted = tuple(transfer.accepted_event for transfer in transfers)
        if all(event is not None for event in accepted):
            ticks = tuple(event.tick for event in accepted)
            coverage.record('reached', 'interleaved-history-routing', accepted_ticks=ticks)
            coverage.record('reached', 'protected-history-restored',
                            accepted_ticks=ticks[len(PROFILES):], histories=tuple(h for h, _ in reversed(PROFILES)))
    assert len(ticks) == len(transfers), 'completed predictions require accepted history requests'
    assert ticks == tuple(range(ticks[0], ticks[0] + 2 * len(transfers), 2))
    for (_, direction), prediction in zip(profiles, predictions, strict=True):
        assert (prediction.valid, prediction.taken) == (1, direction)
        assert prediction.meta['providerTakenCtr_value'] == (5 if direction else 2)
        assert prediction.meta['providerUsefulCtr_value'] == 1
    coverage.record('checked', 'interleaved-history-routing', checked_ticks=tuple(
        transfer.completed_event.tick for transfer in transfers))
    coverage.record('checked', 'protected-history-restored')


async def history_ownership(agent, coverage):
    await agent.reset()
    for history, direction in PROFILES:
        cold = await predict(agent, history, direction)
        assert cold.meta['hasProvider'] == 0
        await accepted_learning(agent, history, direction, cold, coverage, allocate=True)
        weak = await predict(agent, history, direction)
        assert weak.meta['hasProvider'] == 1
        assert weak.meta['providerTakenCtr_value'] == (4 if direction else 3)
        coverage.record('checked', 'context-allocation', history=history)
        await accepted_learning(agent, history, direction, weak, coverage, allocate=False)
        strong = await predict(agent, history, direction)
        assert (strong.valid, strong.taken) == (1, direction)
        assert strong.meta['providerTakenCtr_value'] == (5 if direction else 2)
        assert strong.meta['providerUsefulCtr_value'] == 1
        coverage.record('checked', 'context-local-learning', history=history)

    # The reverse half restores earlier contexts after other histories have
    # been learned/read. Its requests must actually be accepted before credit.
    await pipelined_readback(agent, coverage)
