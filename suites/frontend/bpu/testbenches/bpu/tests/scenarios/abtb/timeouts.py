"""Bounded foreground operations; timeout details remain inside the runtime."""
import asyncio
from contextlib import suppress
from toffee import AnyOf
from toffee import ClockCycles
from toffee import TaskComplete
from toffee import WallTimeout


async def bounded(agent, checker, operation, label, cycles=8192):
    task = asyncio.create_task(operation)
    try:
        event = await AnyOf(TaskComplete(task), ClockCycles(agent.dut.clock, cycles), WallTimeout(300))
        if event.source is task:
            checker.raise_failure()
            return event.value
        checker.raise_failure()
        raise AssertionError(dict(case=checker.case, phase=checker.phase, operation=label,
            last_tick=None if not checker.records else checker.records[-1]['tick'], cycle_limit=cycles))
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
