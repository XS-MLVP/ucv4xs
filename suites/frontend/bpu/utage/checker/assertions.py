"""Reusable MicroTAGE allocation and metadata helpers."""

from __future__ import annotations

from suites.frontend.bpu.utage.transaction.types import UtageTraining


def require_hit(prediction) -> None:
    assert prediction.hit == 1, prediction


def counter(prediction) -> int:
    return prediction.meta["abtbResult"][0]["takenCtr_value"]


async def allocate(agent, pc: int, position: int):
    cold = await agent.predict(pc, position, 0)
    assert cold.hit == 0
    await agent.train(UtageTraining(pc, position, 1, cold.meta))
    trained = await agent.predict(pc, position, 0)
    assert (trained.hit, trained.taken) == (1, 1)
    return trained
