from __future__ import annotations

from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.case.definitions import TARGET_A
from bpuverify.ittage.case.definitions import TARGET_B


def require_hit(prediction) -> None:
    assert prediction.hit == 1, prediction


async def allocate(agent):
    cold = await agent.predict(PC)
    await agent.train(IttageTraining(PC, POSITION, TARGET_A, cold.meta, 1))
    prediction = await agent.predict(PC)
    assert prediction.hit == 1
    assert prediction.target == TARGET_A
    return prediction


async def exhaust_allocation_candidates(agent, *, pc: int = PC, position: int = POSITION):
    """Reach a real no-allocation metadata state using successive target misses."""

    prediction = await agent.predict(pc)
    for index in range(5):
        if prediction.meta["allocate"]["valid"] == 0:
            break
        target = (TARGET_A, TARGET_B)[index % 2]
        assert prediction.target != target, prediction
        await agent.train(IttageTraining(pc, position, target, prediction.meta, 1))
        prediction = await agent.predict(pc)
    else:
        raise AssertionError("ITTAGE still exposes an allocation candidate after five misses")
    assert prediction.hit == 1
    assert prediction.meta["provider"]["valid"] == 1
    assert prediction.meta["allocate"]["valid"] == 0
    return prediction


async def prepare_null_highest_provider(agent, *, pc: int, position: int):
    """Use real target errors to make the longest provider rewriteable."""

    prediction = await exhaust_allocation_candidates(agent, pc=pc, position=position)
    cell = prediction.meta["provider"]["bits"]
    for _ in range(4):
        assert prediction.meta["provider"]["valid"] == 1, prediction
        assert prediction.meta["provider"]["bits"] == cell, prediction
        assert prediction.meta["allocate"]["valid"] == 0, prediction
        if prediction.meta["providerCnt_value"] == 0:
            return prediction
        target = TARGET_B if prediction.meta["providerTarget_addr"] == TARGET_A else TARGET_A
        await agent.train(IttageTraining(
            pc, position, target, prediction.meta, int(prediction.target != target),
        ))
        prediction = await agent.predict(pc)
    raise AssertionError(f"ITTAGE highest provider did not reach confidence 0: {prediction!r}")


async def prepare_first_provider(agent, *, pc: int, position: int, target: int):
    """Wait for an actual first-table allocation offer, without altering meta."""

    for _ in range(32):
        cold = await agent.predict(pc)
        assert cold.hit == 0, cold
        if cold.meta["allocate"]["valid"] and cold.meta["allocate"]["bits"] == 0:
            await agent.train(IttageTraining(pc, position, target, cold.meta, 1))
            prediction = await agent.predict(pc)
            assert (prediction.hit, prediction.target) == (1, target), prediction
            assert prediction.meta["provider"] == {"bits": 0, "valid": 1}, prediction
            assert prediction.meta["providerCnt_value"] == 2, prediction
            return prediction
    raise AssertionError(f"ITTAGE did not offer a first-table allocation for {pc=:#x}")


def require_snapshot(actual, expected):
    """Ignore changing allocation offers/debug cycles, compare resident state."""

    assert (actual.hit, actual.target) == (expected.hit, expected.target), (expected, actual)
    for field in ("provider", "providerCnt_value", "providerTarget_addr", "providerUsefulCnt_value"):
        assert actual.meta[field] == expected.meta[field], (field, expected, actual)
    assert actual.meta["altProvider"]["valid"] == expected.meta["altProvider"]["valid"], (expected, actual)
    if expected.meta["altProvider"]["valid"]:
        for field in ("altProvider", "altProviderCnt_value", "altProviderTarget_addr"):
            assert actual.meta[field] == expected.meta[field], (field, expected, actual)


async def train_no_allocation_misses(agent, prediction, *, count: int):
    """Age with actual no-allocation metadata and a new wrong target each time."""

    if count <= 0:
        raise ValueError("count must be positive")
    last_target = None
    for index in range(count):
        assert prediction.hit == 1, (index, prediction)
        assert prediction.meta["allocate"]["valid"] == 0, (index, prediction)
        last_target = 0x4002_0000 + index * 0x20
        assert last_target != prediction.target, (index, prediction)
        assert last_target != prediction.meta["providerTarget_addr"], (index, prediction)
        await agent.train(
            IttageTraining(PC, POSITION, last_target, prediction.meta, 1)
        )
        prediction = await agent.predict(PC)
    return prediction, last_target
