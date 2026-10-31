"""Typed producers and observations shared by the FTQ tests."""

from __future__ import annotations

from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.ftq.agent.main import FtqAgent
from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.resolve_queue.checker.model import ResolveChecker
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport
from suites.frontend.ftq.ftq.transaction.types import PredictionSpec


async def allocate(agent: FtqAgent, count: int, *, base: int = 0x8000_1000,
                   step: int = 0x20, end_position: int = 3, taken: int = 1,
                   consume: bool = False, with_meta: bool = True,
                   meta_limit: int | None = None, start_index: int = 0,
                   start_flag: int = 0) -> list[PredictionSpec]:
    specs = [PredictionSpec(base + index * step, taken=taken,
                            end_position=end_position)
             for index in range(count)]
    await agent.allocate(specs, consume=consume, with_meta=with_meta,
                         meta_limit=meta_limit, start_index=start_index,
                         start_flag=start_flag)
    return specs


def callret(index: int, ras_action: int) -> CallRet:
    return CallRet(ptr=index, ras=ras_action)


def resolve(index: int, **kwargs) -> ResolveReport:
    return ResolveReport(
        index=index,
        pc=kwargs.pop("pc", 0x8000_1000),
        offset=kwargs.pop("offset", 1),
        target=kwargs.pop("target", 0x8000_3000),
        **kwargs,
    )


def branches(agent: FtqAgent) -> list[tuple[int, int]]:
    training = agent.training()
    return [] if training is None else [
        (branch.position, branch.target) for branch in training.branches]


def resolve_checker(agent: FtqAgent) -> ResolveChecker:
    return ResolveChecker()


def commit_checker() -> CommitChecker:
    return CommitChecker()
