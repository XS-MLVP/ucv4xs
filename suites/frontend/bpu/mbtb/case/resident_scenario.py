"""Prepare real resident pairs and check pipelined, full-state readback."""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace

from suites.frontend.bpu.mbtb.transaction.types import MbtbTraining
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_counter
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.case.definitions import BranchVector


INDEX_CONTEXTS = ((1, 2, 3), (31, 32, 33))
READ_WINDOW = 24


def snapshot(prediction):
    return {"entries": prediction.entries, "meta_entries": deepcopy(prediction.meta_entries)}


def frozen_check(wanted):
    expected = deepcopy(wanted)

    def check(prediction):
        actual = snapshot(prediction)
        assert actual == expected, {"expected": expected, "actual": actual}

    return check


async def read_expected(agent, vectors, states, *, reverse=False):
    indices = tuple(reversed(range(4))) if reverse else tuple(range(4))
    transfers = [agent.submit_predict(vectors[index].pc, expected=frozen_check(states[index]))
                 for index in indices]
    await agent.drain_predictions()
    for transfer in transfers:
        await transfer
        assert transfer.completed_event.tick - transfer.accepted_event.tick == 4
    assert all(second.accepted_event.tick - first.accepted_event.tick == 2
               for first, second in zip(transfers, transfers[1:]))


def resident_vectors(context, align, bank, *, target_type=1, tag_stride=0):
    if not isinstance(tag_stride, int) or tag_stride < 0:
        raise ValueError("resident tag stride must be a nonnegative integer")
    first, second, sentinel = INDEX_CONTEXTS[context]
    return tuple(BranchVector(
        0x40000000 + (index << 7) + (internal_bank << 5) + (ordinal * tag_stride << 15),
        0x40009000 + (index << 6) + (internal_bank << 8),
        1 + ALIGN_HALFWORDS * align, target_type,
    ) for ordinal, (index, internal_bank) in enumerate(((first, bank), (second, bank),
                                                       (sentinel, bank), (sentinel, bank ^ 1))))


async def allocate_pair(agent, vector, way, *, neighbor_type=1):
    if way not in range(MAIN_WAYS):
        raise ValueError('physical MainBTB way required')
    # Populate all four ways in independently known reset-LRU order. Every
    # non-target entry remains a readback sentinel across subsequent writes.
    by_way = {way: vector}
    others = [index for index in range(MAIN_WAYS) if index != way]
    for offset, owner in enumerate(others, 1):
        by_way[owner] = replace(vector, target=vector.target + 0x400 * offset,
                               position=vector.position + offset, branch_type=neighbor_type)
    for owner in reversed(range(MAIN_WAYS)):
        newcomer = by_way[owner]
        cold = await agent.predict(newcomer.pc)
        assert not any(entry.valid and entry.position == newcomer.position for entry in cold.entries)
        await agent.train(MbtbTraining(newcomer.pc, newcomer.target, 1, newcomer.position,
                                      newcomer.branch_type, cold.meta_entries, mispredict=1))
    prediction = await agent.predict(vector.pc)
    align = vector.position // ALIGN_HALFWORDS
    assert sum(entry.valid for entry in prediction.entries) == MAIN_WAYS
    for owner, expected in by_way.items():
        assert_vector_hit(prediction, expected)
        assert matching_counter(prediction, expected) == 2
        assert matching_way(prediction, expected) == align * (MAIN_WAYS + 1) + owner
    return prediction


async def prepare(agent, context, align, bank, way, *, target_type=1, neighbor_type=1, tag_stride=0):
    vectors = resident_vectors(context, align, bank, target_type=target_type, tag_stride=tag_stride)
    await agent.reset()
    prepared = [await allocate_pair(agent, vector, way, neighbor_type=neighbor_type) for vector in vectors]
    return vectors, prepared
