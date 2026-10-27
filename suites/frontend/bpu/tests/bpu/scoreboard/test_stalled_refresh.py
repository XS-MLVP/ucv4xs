"""A bounded refresh does not add an empirical ready-high wait."""
from types import SimpleNamespace

import pytest

from bpuverify.bpu.agent.main import BpuAgent


@pytest.mark.parametrize('fail_launch', (False, True))
async def test_refresh_uses_minimum_control_launch_and_restores_backpressure(fail_launch):
    launches = []
    sample = object()
    agent = SimpleNamespace(_prediction_ready=0, _meta_ready=0,
        _require_started=lambda: None, sample_stalled_prediction=lambda: sample)

    async def drive(*, cycles):
        launches.append((agent._prediction_ready, agent._meta_ready, cycles))
        if fail_launch and agent._prediction_ready:
            raise RuntimeError('injected control launch failure')
    agent._drive_control = drive
    if fail_launch:
        with pytest.raises(RuntimeError, match='injected control launch failure'):
            await BpuAgent.refresh_stalled_prediction(agent)
    else:
        assert await BpuAgent.refresh_stalled_prediction(agent) is sample
    assert launches == [(1, 1, 0), (0, 1, 0)]
    assert agent._prediction_ready == 0


async def test_refresh_requires_existing_backpressure_before_driving():
    agent = SimpleNamespace(_prediction_ready=1, _require_started=lambda: None)
    with pytest.raises(RuntimeError, match='already be backpressured'):
        await BpuAgent.refresh_stalled_prediction(agent)


async def test_ready_returns_the_control_drivers_commit_boundary():
    launches = []
    agent = SimpleNamespace(_require_started=lambda: None)

    async def drive():
        launches.append((agent._prediction_ready, agent._meta_ready))
        return SimpleNamespace(tick=42)

    agent._drive_control = drive
    assert await BpuAgent.set_ready(agent, prediction=True, meta=False) == 42
    assert launches == [(1, 0)]
