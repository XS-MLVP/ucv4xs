"""Normal feedback proves indexed LRU sharing, qualification and isolation."""
from copy import deepcopy
from dataclasses import replace

from bpuverify.mbtb.transaction.types import MbtbTraining
from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.model.replacement import MbtbReplacementState
from bpuverify.mbtb.model.replacement import expected_mbtb_replacement_feedback
from bpuverify.mbtb.model.replacement import expected_mbtb_replacement_state
from bpuverify.mbtb.model.replacement import mbtb_replacement_geometry
from bpuverify.mbtb.checker.assertions import matching_entry
from bpuverify.mbtb.checker.assertions import matching_counter
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.resident_scenario import frozen_check
from bpuverify.mbtb.case.resident_scenario import snapshot


TOUCH_MODES = ('taken_way0', 'taken_way1', 'not_taken', 'lookup_only')
PHASES = ('prepared', 'qualified', 'replaced', 'alias_replaced', 'isolated', 'revisited')


def replacement_vectors(index, align, upper):
    if not isinstance(index, int) or not 0 <= index < 64 or align not in (0, 1) or upper not in (0, 1):
        raise ValueError('replacement scenario requires index 0..63 and alignment/upper-set bit 0/1')
    pc = 0x40001000 + (index << 4) + (upper << 10)
    return tuple(BranchVector(address, 0x40009000 + ordinal * 0x1000, 1 + 8 * row, 1)
                 for ordinal, (address, row) in enumerate(((pc, align), (pc ^ 0x400, align),
                                                           (pc ^ 0x20, align), (pc, 1 - align))))


async def read_profiles(agent, vectors, states, *, reverse=False):
    indices = tuple(reversed(range(4))) if reverse else tuple(range(4))
    transfers = [agent.submit_predict(vectors[index].pc, expected=frozen_check(states[vectors[index].pc]))
                 for index in indices]
    await agent.drain_predictions()
    for transfer in transfers:
        await transfer
        assert transfer.completed_event.tick - transfer.accepted_event.tick == 4
    assert all(second.accepted_event.tick - first.accepted_event.tick == 2
               for first, second in zip(transfers, transfers[1:]))


async def allocate(agent, model, vector):
    before = await agent.predict(vector.pc)
    assert not any(entry.valid and entry.position == vector.position for entry in before.entries)
    wanted_way = model.allocate(vector.pc, vector.position)
    await agent.train(MbtbTraining(vector.pc, vector.target, 1, vector.position, 1,
                                  deepcopy(before.meta_entries), mispredict=1))
    after = await agent.predict(vector.pc)
    assert matching_entry(after, vector) == MbtbEntry(1, 1, vector.target, vector.position, 1, 0)
    assert matching_way(after, vector) == 2 * (vector.position // 8) + wanted_way
    assert matching_counter(after, vector) == 2
    return after


async def check_case(agent, coverage, index, align, upper, mode):
    if mode not in TOUCH_MODES:
        raise ValueError('unknown replacement touch mode')
    vectors = replacement_vectors(index, align, upper)
    await agent.reset()
    model = MbtbReplacementState()
    residents = []
    for vector in vectors:
        pair = (vector, replace(vector, position=vector.position + 1, target=vector.target + 0x400))
        residents.extend(pair)
        for newcomer in pair:
            await allocate(agent, model, newcomer)
    states = {vector.pc: snapshot(await agent.predict(vector.pc)) for vector in vectors}
    # Verify every installed payload and way before adopting only unchanged
    # snapshot fields (including reset-defined invalid output bits).
    for ordinal, vector in enumerate(residents):
        prediction = await agent.predict(vector.pc)
        assert matching_entry(prediction, vector) == MbtbEntry(1, 1, vector.target, vector.position, 1, 0)
        assert matching_way(prediction, vector) == 2 * (vector.position // 8) + (1 if ordinal % 2 == 0 else 0)
        assert matching_counter(prediction, vector) == 2
    sample = dict(index=index, align=align, upper=upper, mode=mode)
    await read_profiles(agent, vectors, states)
    coverage.sample(dict(sample, phase='prepared'))

    alias = vectors[1]
    if mode == 'taken_way0':
        # Both setup allocations end with way0 touched. A second way0 touch
        # would otherwise leave the age unchanged and fail to prove it works.
        # Steer with genuine correct-taken way1 feedback first, then test the
        # way0 transition from its discriminating opposite age.
        opposite = expected_mbtb_replacement_feedback(states[alias.pc], align, 1, taken=1)
        model.feedback(alias.pc, alias.position, 1, taken=1)
        await agent.train(MbtbTraining(alias.pc, alias.target, 1, alias.position, 1,
                                      deepcopy(states[alias.pc]['meta_entries']), mispredict=0))
        states[alias.pc] = opposite
        await read_profiles(agent, vectors, states)
    before_victim = model.victim(alias.pc, alias.position)
    touch_way = 0 if mode == 'taken_way0' else 1
    touched = replace(alias, position=alias.position + int(touch_way == 0),
                      target=alias.target + 0x400 * int(touch_way == 0))
    if mode == 'lookup_only':
        await agent.predict(alias.pc)
    else:
        taken = int(mode != 'not_taken')
        wanted_touch = expected_mbtb_replacement_feedback(states[alias.pc], align, touch_way, taken=taken)
        model.feedback(touched.pc, touched.position, touch_way, taken=taken)
        # A weak-positive conditional predicts taken: actual NT is a real
        # misprediction, while a correct taken feedback has mispredict=0.
        await agent.train(MbtbTraining(touched.pc, touched.target, taken, touched.position, 1,
                                      deepcopy(states[alias.pc]['meta_entries']), mispredict=1 - taken))
        states[alias.pc] = wanted_touch
    after_victim = model.victim(alias.pc, alias.position)
    assert (before_victim != after_victim) == (mode in ('taken_way0', 'taken_way1'))
    await read_profiles(agent, vectors, states)
    coverage.sample(dict(sample, phase='qualified'))

    for ordinal, vector in enumerate(vectors):
        newcomer = replace(vector, position=vector.position + 2, target=vector.target + 0x800)
        # Freeze the complete expected result before sending fresh, normal
        # feedback. A and its set+32 alias share LRU, C and D do not.
        geometry = mbtb_replacement_geometry(vector.pc, vector.position)
        way = model.allocate(vector.pc, vector.position)
        expected = expected_mbtb_replacement_state(states[vector.pc], geometry.align, way, newcomer)
        before = await agent.predict(vector.pc)
        frozen_check(states[vector.pc])(before)
        await agent.train(MbtbTraining(newcomer.pc, newcomer.target, 1, newcomer.position, 1,
                                      deepcopy(before.meta_entries), mispredict=1))
        states[vector.pc] = expected
        await read_profiles(agent, vectors, states)
        if ordinal < 2:
            coverage.sample(dict(sample, phase='replaced' if ordinal == 0 else 'alias_replaced'))
    coverage.sample(dict(sample, phase='isolated'))
    await read_profiles(agent, vectors, states, reverse=True)
    coverage.sample(dict(sample, phase='revisited'))
