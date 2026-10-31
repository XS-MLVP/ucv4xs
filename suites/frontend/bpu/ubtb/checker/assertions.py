"""Reusable MicroBTB transactions and domain assertions."""

from __future__ import annotations

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining
from suites.frontend.bpu.ubtb.transaction.types import UbtbPrediction
from suites.frontend.bpu.ubtb.case.definitions import BranchVector


def expected_prediction(vector: BranchVector) -> UbtbPrediction:
    return UbtbPrediction(
        valid=1,
        taken=1,
        target=vector.target,
        position=vector.position,
        branch_type=vector.branch_type,
    )


async def train_taken(agent, vector: BranchVector) -> None:
    await agent.train(
        BranchTraining(
            pc=vector.pc,
            target=vector.target,
            taken=1,
            position=vector.position,
            branch_type=vector.branch_type,
        )
    )


async def train_not_taken(agent, vector: BranchVector) -> None:
    await agent.train(
        BranchTraining(
            pc=vector.pc,
            target=vector.target,
            taken=0,
            position=vector.position,
            branch_type=vector.branch_type,
        )
    )


async def assert_hit(agent, vector: BranchVector) -> None:
    actual = await agent.predict(vector.pc)
    expected = expected_prediction(vector)
    assert actual == expected, (
        f"MicroBTB payload mismatch for pc={vector.pc:#x}: "
        f"expected={expected!r}, actual={actual!r}"
    )


async def assert_miss(agent, pc: int) -> None:
    assert (await agent.predict(pc)).valid == 0
