"""Reusable RAS stack actions and assertions."""

from __future__ import annotations

from suites.frontend.bpu.ras.model.addresses import return_addr
from suites.frontend.bpu.ras.case.definitions import CallVector
from suites.frontend.bpu.ras.case.definitions import unique_calls


async def push(agent, vector: CallVector, *, enable: int = 1):
    return await agent.act(
        2,
        start_pc=vector.start_pc,
        position=vector.position,
        enable=enable,
    )


async def pop(agent):
    return await agent.act(1)


def expected_top(vector: CallVector) -> int:
    return return_addr(vector.start_pc, vector.position)


async def committed_round_trips(agent, *, resident_top: int):
    """Reuse more than one spec queue's capacity without losing an old frame."""

    resident = agent.snapshot()
    for call in unique_calls():
        before = agent.snapshot()
        assert (await push(agent, call)).top == expected_top(call)
        assert (await agent.commit(before.commit_meta, action=2)).top == expected_top(call)
        before_return = agent.snapshot()
        assert (await pop(agent)).top == resident_top
        after = await agent.commit(before_return.commit_meta, action=1)
        assert after.top == resident_top
        for field in ("ssp", "sctr"):
            assert after.redirect_meta[field] == resident.redirect_meta[field]
    return agent.snapshot()
