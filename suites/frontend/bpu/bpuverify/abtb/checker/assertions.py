"""Reusable AheadBTB transactions and domain assertions."""

from __future__ import annotations

from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.abtb.case.definitions import NUM_WAYS


def maybe_matching_entry(prediction, position: int, branch_type: int):
    matches = [
        (index, entry)
        for index, entry in enumerate(prediction.entries)
        if entry.valid
        and entry.position == position
        and entry.branch_type == branch_type
    ]
    assert len(matches) <= 1, (
        "expected at most one matching AheadBTB entry: "
        f"position={position}, branch_type={branch_type}, actual={prediction!r}"
    )
    return matches[0] if matches else None


def matching_entry(prediction, position: int, branch_type: int):
    match = maybe_matching_entry(prediction, position, branch_type)
    assert match is not None, (
        "expected one matching AheadBTB entry: "
        f"position={position}, branch_type={branch_type}, actual={prediction!r}"
    )
    return match


def require_valid(prediction) -> None:
    assert any(entry.valid for entry in prediction.entries), prediction


async def train_taken(agent, vector: BranchVector, meta) -> None:
    await agent.train(
        AbtbTraining(
            pc=vector.pc,
            target=vector.target,
            taken=1,
            position=vector.position,
            branch_type=vector.branch_type,
            meta=meta,
        )
    )


async def fill_taken_position_set(agent, vectors, *, path_hash: int = 0):
    """Install one PC's four ordered positions without aging earlier ones."""

    assert len(vectors) == NUM_WAYS
    assert all(vector.pc == vectors[0].pc for vector in vectors)
    positions = [vector.position for vector in vectors]
    assert positions == sorted(set(positions))
    for vector in reversed(vectors):
        before = await agent.predict(vector.pc, path_hash=path_hash)
        await train_taken(agent, vector, before.meta)
        observed = await agent.predict(vector.pc, path_hash=path_hash)
        _, entry = matching_entry(observed, vector.position, vector.branch_type)
        assert (entry.taken, entry.target) == (1, vector.target)

    full = await agent.predict(vectors[0].pc, path_hash=path_hash)
    by_position = {}
    for vector in vectors:
        way, entry = matching_entry(full, vector.position, vector.branch_type)
        assert (entry.taken, entry.target) == (1, vector.target)
        by_position[vector.position] = way
    assert set(by_position.values()) == set(range(NUM_WAYS))
    return full, by_position


def assert_position_directions(prediction, vectors, original_way, expected_taken):
    """Check all same-PC entries without losing type/way/target identity."""

    assert len(vectors) == len(expected_taken) == NUM_WAYS
    assert sum(entry.valid for entry in prediction.entries) == NUM_WAYS
    for vector, taken in zip(vectors, expected_taken, strict=True):
        way, entry = matching_entry(
            prediction, vector.position, vector.branch_type
        )
        assert way == original_way[vector.position]
        assert (entry.taken, entry.target) == (taken, vector.target)


def assert_position_profile(prediction, expected):
    """Check all four resident positions, including physical way and target."""

    assert len(expected) == NUM_WAYS
    assert sum(entry.valid for entry in prediction.entries) == NUM_WAYS
    for position, (vector, way, taken) in expected.items():
        assert vector.position == position
        observed_way, entry = matching_entry(
            prediction, position, vector.branch_type
        )
        assert observed_way == way, (position, observed_way, way, prediction)
        assert (entry.taken, entry.target) == (taken, vector.target), (
            position, entry, (taken, vector.target), prediction
        )


async def train_conditional_direction(agent, vector: BranchVector, prediction, *, taken: int) -> None:
    """Train the observed conditional entry using its matching lookup metadata."""

    assert vector.branch_type == 1
    assert prediction.meta["valid"] == 1
    await agent.train(
        AbtbTraining(
            pc=vector.pc,
            target=vector.target,
            taken=taken,
            position=vector.position,
            branch_type=vector.branch_type,
            meta=prediction.meta,
        )
    )


async def age_conditional_to_not_taken(agent, vector: BranchVector, prediction, *, path_hash: int = 0):
    """Reach negative saturation while retaining the tag and target."""

    for _ in range(3):
        await train_conditional_direction(agent, vector, prediction, taken=0)
        prediction = await assert_conditional_state(
            agent, vector, taken=0, path_hash=path_hash
        )
    return prediction


def assert_vector_hit(prediction, vector: BranchVector) -> None:
    _, hit = matching_entry(prediction, vector.position, vector.branch_type)
    assert hit.taken == 1
    assert hit.target == vector.target


async def assert_conditional_state(agent, vector: BranchVector, *, taken: int, path_hash: int = 0):
    prediction = await agent.predict(vector.pc, path_hash=path_hash)
    _, entry = matching_entry(prediction, vector.position, vector.branch_type)
    assert entry.taken == taken, (vector, prediction)
    assert entry.target == vector.target, (vector, prediction)
    return prediction


def assert_miss(prediction) -> None:
    assert not any(entry.valid for entry in prediction.entries), prediction
