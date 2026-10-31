"""ResolveQueue randomized ownership against the independent merge model."""

from __future__ import annotations

import random

import pytest

from tests.resolve_queue.support import report

pytestmark = [pytest.mark.feature("FTQ-RQ-002"),
              pytest.mark.feature("FTQ-RQ-003")]

PCS = [0x8000_0000 + index * 0x20 for index in range(8)]


def _spec(rng: random.Random) -> dict[str, int]:
    return dict(
        offset=rng.randrange(32),
        target=0x9000_0000 + rng.randrange(0x4000),
        taken=rng.randrange(2),
        mispredict=rng.randrange(2),
        branch_type=rng.randrange(4),
        ras_action=rng.randrange(4),
    )


async def test_random_ownership_sequence_matches_merge_oracle(resolve_queue_agent):
    agent = resolve_queue_agent
    checker = agent.checker
    rng = random.Random(0x5EED)
    await agent.ready(False)

    for _ in range(180):
        action = rng.choices(["push", "drain", "idle"], weights=[6, 2, 1])[0]
        if action == "push":
            index = rng.randrange(8)
            room = checker.room(index)
            backend = []
            ifu = None
            for lane in range(3):
                if rng.random() >= 0.55:
                    continue
                spec = _spec(rng)
                accepted = checker.accepts(report(index, **spec))
                if accepted and room <= 0:
                    continue
                item = report(index, **spec)
                backend.append(item)
                checker.push(item, source=f"backend{lane}")
                if accepted:
                    room -= 1
            if rng.random() < 0.35 and room > 0:
                spec = _spec(rng)
                ifu = report(index, **spec)
                checker.push(ifu, source="ifu")
                room -= 1
            if backend or ifu is not None:
                await agent.resolve_mixed(backend, ifu)
            else:
                await agent.step(1)
            checker.check(agent.training())
            # Keep the randomized sequence below the declared guard so that
            # capacity overflow (FTQ-RQ-011) is not mixed into this oracle.
            while checker.model.depth >= 6:
                checker.check(agent.training())
                await agent.drain()
                checker.pop()
                checker.check(agent.training())
        elif action == "idle":
            await agent.step(1)
            checker.check(agent.training())

    for _ in range(20):
        if checker.head() is None:
            break
        checker.check(agent.training())
        await agent.drain()
        checker.pop()
    await agent.step(2)
    assert agent.training() is None
    assert checker.head() is None
