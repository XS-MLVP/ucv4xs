"""Instruction/history programs; agents own timing and models own expected state."""
from suites.frontend.bpu.utage.transaction.types import UtageTraining


PC = 0x40000000
POSITION = 5
MAX_INDEX_PC = PC + (1 << 9) - 1


async def boundary_lifecycle(agent, coverage):
    await agent.reset()

    async def read(base, *, history=0):
        return await agent.predict(PC, POSITION, base, folded_history=history,
                                   index_pc=MAX_INDEX_PC, index_history=0)

    async def send(source, taken, rule, expected_useful):
        first = len(agent.training_observations)
        try:
            await agent.train(UtageTraining(PC, POSITION, taken, source.meta))
        finally:
            offered = agent.training_observations[first:]
            if offered:
                assert len(offered) == 1
                coverage.record('reached', rule, offered_tick=offered[0].event.tick, index=511)
        agent.check_useful(0, 511, expected_useful)
        coverage.record('checked', rule, checked_tick=agent.reference.last_event.tick, index=511)
        if rule == 'short-allocation':
            coverage.physical_allocation.sample(dict(mode='serial', table=0, index=511))
        elif rule == 'useful-positive-saturation':
            role = 'increase_hold' if expected_useful == 3 and source.meta['abtbResult'][0]['takenCtr_value'] == 1 else 'increase'
            coverage.physical_update.sample(dict(mode='serial', table=0, index=511, role=role))
        elif rule == 'useful-zero-hold':
            coverage.physical_update.sample(dict(mode='serial', table=0, index=511, role='decrease_hold'))

    cold = await read(1)
    assert cold.hit == 0 and tuple(cold.meta['readIndex']) == (511, 511)
    coverage.record('reached', 'split-source', index=511)
    coverage.record('checked', 'split-source', index=511)
    await send(cold, 0, 'short-allocation', 1)
    for useful, counter in ((2, 2), (3, 1), (3, 0)):
        source = await read(1)
        assert source.hit == 1 and source.meta['abtbResult'][0]['tableId'] == 0
        await send(source, 0, 'useful-positive-saturation', useful)
        fresh = await read(1)
        assert fresh.meta['abtbResult'][0]['takenCtr_value'] == counter
    source = await read(0)
    await send(source, 0, 'base-agreement-hold', 3)

    # Three genuine source snapshots precede the burst. Their stale counter
    # metadata is unmodified; accepted feedback must forward its predecessor
    # counter update and use current usefulness, not replay the old count.
    transfers = [agent.submit_predict(PC, POSITION, 1, index_pc=MAX_INDEX_PC, index_history=0)
                 for _ in range(3)]
    await agent.drain_predictions()
    sources = [await transfer for transfer in transfers]
    first = len(agent.training_observations)
    try:
        await agent.train_many(tuple(UtageTraining(PC, POSITION, 1, source.meta) for source in sources))
    finally:
        offered = agent.training_observations[first:]
        if offered:
            coverage.record('reached', 'adjacent-negative-chain', offers=len(offered), index=511)
    assert len(offered) == 3
    ticks = [row.event.tick for row in offered]
    assert ticks == list(range(ticks[0], ticks[0] + 6, 2))
    agent.check_useful(0, 511, 0)
    coverage.record('checked', 'adjacent-negative-chain', offers=3, index=511)
    coverage.physical_update.sample(dict(mode='adjacent', table=0, index=511, role='decrease'))

    upper = await read(1)
    assert upper.hit == 1 and upper.taken == 1
    assert upper.meta['abtbResult'][0]['tableId'] == 1
    assert upper.meta['abtbResult'][0]['takenCtr_value'] == 4
    agent.check_useful(1, 511, 2)
    coverage.record('reached', 'long-provider-selected', index=511)
    coverage.record('checked', 'long-provider-selected', index=511)
    coverage.physical_allocation.sample(dict(mode='adjacent', table=1, index=511))

    # Bit6 is outside the short history but inside the long history. Keep the
    # A0 maximum index fixed and retag A1 independently to expose the retained
    # short entry after a long entry has become the usual provider.
    lower = await read(1, history=64)
    assert lower.hit == 1 and lower.taken == 0
    assert lower.meta['abtbResult'][0]['tableId'] == 0
    assert lower.meta['abtbResult'][0]['takenCtr_value'] == 3
    await send(lower, 1, 'useful-zero-hold', 0)
    expected = [await read(1, history=history) for history in (0, 64)]
    histories = (0, 64, 0, 64, 0, 64)
    transfers = [agent.submit_predict(PC, POSITION, 1, folded_history=history,
                                     index_pc=MAX_INDEX_PC, index_history=0) for history in histories]
    await agent.drain_predictions()
    values = [await transfer for transfer in transfers]
    assert [value.meta for value in values] == [expected[int(history != 0)].meta for history in histories]
    assert all(tuple(value.meta['readIndex']) == (511, 511) for value in values)
    coverage.record('reached', 'interleaved-context-association', histories=histories, index=511)
    coverage.record('checked', 'interleaved-context-association', histories=histories, index=511)
    assert agent.reference.board.status.failed == 0


async def nonconditional_feedback(agent, coverage, *, kind):
    await agent.reset()
    cold = await agent.predict(PC, POSITION, 1)
    await agent.train(UtageTraining(PC, POSITION, 0, cold.meta))
    source = await agent.predict(PC, POSITION, 1)
    assert source.hit == 1 and source.taken == 0
    assert source.meta['abtbResult'][0]['takenCtr_value'] == 3
    agent.check_useful(0, 0, 1)
    rule = 'resolved-direct-same-position' if kind == 2 else 'resolved-indirect-same-position'
    first = len(agent.training_observations)
    try:
        await agent.train(UtageTraining(PC, POSITION, 1, source.meta, branch_type=kind))
    finally:
        offered = agent.training_observations[first:]
        if offered:
            assert len(offered) == 1
            coverage.record('reached', rule, offered_tick=offered[0].event.tick)
    agent.check_useful(0, 0, 1)
    actual = await agent.predict(PC, POSITION, 1)
    assert actual.meta['abtbResult'][0]['takenCtr_value'] == 3
    coverage.record('checked', rule, checked_tick=agent.reference.last_event.tick)
