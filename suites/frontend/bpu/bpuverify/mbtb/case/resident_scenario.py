"""Prepare real resident pairs and check pipelined, full-state readback."""
from copy import deepcopy
from dataclasses import replace

from bpuverify.mbtb.transaction.types import MbtbTraining
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import matching_counter
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.case.definitions import BranchVector


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
        0x40001000 + (index << 5) + (internal_bank << 4) + (ordinal * tag_stride << 11),
        0x40009000 + (index << 6) + (internal_bank << 8),
        1 + 8 * align, target_type,
    ) for ordinal, (index, internal_bank) in enumerate(((first, bank), (second, bank),
                                                       (sentinel, bank), (sentinel, 1 - bank))))


async def allocate_pair(agent, vector, way, *, neighbor_type=1):
    neighbor = replace(vector, target=vector.target + 0x400, position=vector.position + 1,
                       branch_type=neighbor_type)
    # Reset LRU selects way 1. Two normal allocations place the target
    # in either way and retain a separately checked opposite-way resident.
    ordered = (vector, neighbor) if way == 1 else (neighbor, vector)
    for newcomer in ordered:
        cold = await agent.predict(newcomer.pc)
        assert not any(entry.valid and entry.position == newcomer.position for entry in cold.entries)
        await agent.train(MbtbTraining(newcomer.pc, newcomer.target, 1, newcomer.position,
                                      newcomer.branch_type, cold.meta_entries, mispredict=1))
    prediction = await agent.predict(vector.pc)
    align = vector.position // 8
    assert sum(entry.valid for entry in prediction.entries) == 2
    assert_vector_hit(prediction, vector)
    assert_vector_hit(prediction, neighbor)
    assert matching_counter(prediction, vector) == matching_counter(prediction, neighbor) == 2
    assert matching_way(prediction, vector) == align * 2 + way
    assert matching_way(prediction, neighbor) == align * 2 + 1 - way
    return prediction


async def prepare(agent, context, align, bank, way, *, target_type=1, neighbor_type=1, tag_stride=0):
    vectors = resident_vectors(context, align, bank, target_type=target_type, tag_stride=tag_stride)
    await agent.reset()
    prepared = [await allocate_pair(agent, vector, way, neighbor_type=neighbor_type) for vector in vectors]
    return vectors, prepared
