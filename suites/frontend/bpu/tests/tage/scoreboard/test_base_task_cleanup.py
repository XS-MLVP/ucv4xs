import asyncio
from types import SimpleNamespace

import pytest

from bpuverify.tage.agent.main import TageAgent


def owner(tasks, first_failure=None):
    return SimpleNamespace(_base_tasks=set(tasks),
                           prediction_scoreboard=SimpleNamespace(status=SimpleNamespace(first_failure=first_failure)))


async def fail(error):
    raise error


async def test_cleanup_consumes_only_duplicate_owned_failure():
    error = AssertionError('already reported by prediction Scoreboard')
    task = asyncio.create_task(fail(error))
    await asyncio.sleep(0)
    agent = owner((task,), error)
    await TageAgent._close_base_tasks(agent)
    assert not agent._base_tasks and task.done()


async def test_cleanup_preserves_unexpected_secondary_failure_and_reclaims_all_tasks():
    known, unexpected = AssertionError('owned'), RuntimeError('independent secondary failure')
    tasks = tuple(asyncio.create_task(fail(error)) for error in (known, unexpected))
    await asyncio.sleep(0)
    agent = owner(tasks, known)
    with pytest.raises(RuntimeError, match='independent secondary failure'):
        await TageAgent._close_base_tasks(agent)
    assert not agent._base_tasks and all(task.done() for task in tasks)


async def test_cleanup_cancels_unfinished_secondary_task():
    event = asyncio.Event()
    task = asyncio.create_task(event.wait())
    await asyncio.sleep(0)
    agent = owner((task,))
    await TageAgent._close_base_tasks(agent)
    assert not agent._base_tasks and task.cancelled()
