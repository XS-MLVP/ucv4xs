"""Two target corrections under read pressure, without physical enumeration."""
from bpuverify.abtb.transaction.types import AbtbTraining


PC = 0x40000800
POSITIONS = (3, 9)
TARGETS = (PC + 0x180, PC + 0x280)


def targets(prediction):
    result = {entry.position: entry.target for entry in prediction.entries if entry.valid}
    assert set(result) == set(POSITIONS)
    assert all(entry.branch_type == 3 and entry.ras_action == 0
               for entry in prediction.entries if entry.valid)
    return result


async def resident_sources(agent):
    await agent.reset()
    # These are independent UT feedback inputs, not a claim that two taken
    # indirects execute in one FTQ block. Every source snapshot is genuine and
    # has already been compared by the independent prediction model.
    for position, target in zip(POSITIONS, TARGETS, strict=True):
        before = await agent.predict(PC)
        await agent.train(AbtbTraining(PC, target, 1, position, 3, before.meta))
    source = await agent.predict(PC)
    assert targets(source) == dict(zip(POSITIONS, TARGETS, strict=True))
    return source


async def serial_corrections(agent):
    source = await resident_sources(agent)
    expected = dict(zip(POSITIONS, TARGETS, strict=True))
    for position, target in ((POSITIONS[0], TARGETS[0] + 0x40), (POSITIONS[1], TARGETS[1] + 0x80)):
        await agent.train(AbtbTraining(PC, target, 1, position, 3, source.meta))
        expected[position] = target
        source = await agent.predict(PC)
        assert targets(source) == expected
    # Deliberately no pending/overlap coverage credit from this serial control.


async def pending_corrections(agent, coverage, *, distinct):
    source = await resident_sources(agent)
    rule = 'distinct-destinations-retained' if distinct else 'same-destination-latest'
    second_position = POSITIONS[1] if distinct else POSITIONS[0]
    changes = ((POSITIONS[0], TARGETS[0] + 0x40), (second_position, TARGETS[1] + 0x80))
    first_tick = agent.reference.input_tick
    try:
        for position, target in changes:
            await agent.train_under_read_pressure(AbtbTraining(PC, target, 1, position, 3, source.meta))
        stalled = await agent.predict(PC)
        assert targets(stalled) == dict(zip(POSITIONS, TARGETS, strict=True))
        await agent.drain_bank_writes()
    finally:
        accepted = [(tick, request) for tick, request in agent.reference.accepted_feedback if tick > first_tick]
        if len(accepted) == 2:
            assert [(request.position, request.target) for _, request in accepted] == list(changes)
            assert len({(request.banks, request.row) for _, request in accepted}) == 1
            assert all(request.pc == PC and request.kind == 3 and request.action == 0 for _, request in accepted)
            coverage.record('reached', rule, offered_ticks=tuple(tick for tick, _ in accepted),
                            destinations=tuple(request.position for _, request in accepted))
    expected = dict(zip(POSITIONS, TARGETS, strict=True))
    expected.update(changes)
    observed = await agent.predict(PC)
    assert targets(observed) == expected
    coverage.record('checked', rule, checked_tick=agent.reference.input_tick + 1,
                    positions=POSITIONS, targets=tuple(expected[position] for position in POSITIONS))
