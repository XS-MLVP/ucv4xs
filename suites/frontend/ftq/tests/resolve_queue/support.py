"""Typed request builders shared by the ResolveQueue tests."""

from __future__ import annotations

from suites.frontend.ftq.resolve_queue.agent.main import ResolveQueueAgent
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport

PC0 = 0x8000_1000


def report(index: int, **kwargs) -> ResolveReport:
    return ResolveReport(
        index=index,
        pc=kwargs.pop("pc", PC0),
        offset=kwargs.pop("offset", 1),
        target=kwargs.pop("target", 0x8000_3000),
        **kwargs,
    )


def head(agent: ResolveQueueAgent) -> tuple[int, int, int] | None:
    training = agent.training()
    if training is None:
        return None
    return (training.index, training.flag, training.start_pc)


def positions(agent: ResolveQueueAgent) -> list[int]:
    training = agent.training()
    return [] if training is None else [branch.position for branch in training.branches]
