"""Completion follows status, not elapsed sleeps or input readiness."""
import asyncio

import pytest
from toffee import Bundle, ClockCycles, Execution, MemoryBackend
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.activity import ActivityMonitor
from tests.framework.fakes import Signal


def monitor():
    clock, stage, dirty = object(), Signal(1), Signal(1)
    binding = PortBinding(clock, Bundle(pipeline=(stage,), writes=(dirty,)), 'training')
    activity = ActivityMonitor((binding, dict(pipeline=('t1_valid',), writes=('buffer_pending',))))
    return clock, stage, dirty, activity


async def test_early_ready_or_pipeline_retirement_is_not_write_completion():
    clock, stage, dirty, activity = monitor()
    async with Execution(MemoryBackend(clock)):
        async def hardware():
            await ClockCycles(clock, 2)
            stage.Set(0)
            await ClockCycles(clock, 5)
            dirty.Set(0)
        task = asyncio.create_task(hardware())
        retired = await activity.wait_idle('pipeline')
        assert dirty.U() == 1
        committed = await activity.wait_idle('pipeline', 'writes')
        assert committed.tick > retired.tick
        assert committed.state == dict(pipeline={}, writes={})
        await task


async def test_already_idle_still_observes_a_registered_sample():
    clock, stage, dirty, activity = monitor()
    stage.Set(0); dirty.Set(0)
    async with Execution(MemoryBackend(clock)):
        result = await activity.wait_idle()
        assert result.samples >= 1 and result.tick > 0


async def test_stuck_status_raises_with_name_tick_and_pending_state():
    clock, stage, dirty, activity = monitor()
    stage.Set(0)
    async with Execution(MemoryBackend(clock)):
        with pytest.raises(TimeoutError, match=r'training.idle.*last_state=.*buffer_pending'):
            await activity.wait_idle(timeout_cycles=3)


@pytest.mark.parametrize('budget', (0, -1, True, 1.5))
async def test_invalid_budget_rejected(budget):
    _, _, _, activity = monitor()
    with pytest.raises(ValueError):
        await activity.wait_idle(timeout_cycles=budget)
