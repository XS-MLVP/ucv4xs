"""Active-stream retirement and read-free commit are different promises."""
from types import SimpleNamespace

import pytest

from bpuverify.bpu.agent.main import BpuAgent


def agent_with_pending_writes():
    agent = object.__new__(BpuAgent)
    agent._started = True
    agent._single_training = lambda tx: tx
    calls = []
    async def wait_idle(*groups):
        calls.append(groups)
    async def send(tx):
        return SimpleNamespace(tick=2)
    agent.training_activity = SimpleNamespace(wait_idle=wait_idle)
    agent.training_driver = SimpleNamespace(send=send)
    return agent, calls


async def test_active_prediction_training_does_not_require_pending_sram_to_commit():
    agent, calls = agent_with_pending_writes()
    await agent.train_batches((object(),))
    assert calls == [('pipeline',)]


@pytest.mark.parametrize('method', ('train', 'train_batch'))
async def test_serial_training_establishes_read_free_commit_and_restores_flow(method):
    agent, calls = agent_with_pending_writes()
    agent._prediction_ready = agent._meta_ready = 1
    controls = []
    async def set_ready(**values):
        controls.append(values)
    agent.set_ready = set_ready
    await getattr(agent, method)(object(), prediction_pause=True)
    assert calls == [('reads',), ('pipeline', 'writes'), ('pipeline', 'writes')]
    assert controls == [dict(prediction=False, meta=True), dict(prediction=True, meta=True)]


@pytest.mark.parametrize('method', ('train', 'train_batch'))
async def test_active_serial_commit_keeps_prediction_control_unchanged(method):
    agent, calls = agent_with_pending_writes()
    await getattr(agent, method)(object())
    assert calls == [('pipeline', 'writes')]


async def test_read_free_batch_training_still_requires_real_commit():
    agent, calls = agent_with_pending_writes()
    agent._prediction_ready = agent._meta_ready = 1
    controls = []
    async def set_ready(**values):
        controls.append(values)
    agent.set_ready = set_ready
    ticks = await agent.train_batches_with_prediction_pause((object(),))
    assert ticks == (2,)
    assert calls == [('reads',), ('pipeline',), ('pipeline', 'writes')]
    assert controls == [dict(prediction=False, meta=True), dict(prediction=True, meta=True)]
