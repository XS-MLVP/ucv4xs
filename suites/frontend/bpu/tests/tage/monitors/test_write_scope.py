"""Observation scope restores lifecycle state on every exit path."""
from types import SimpleNamespace

import pytest

from bpuverify.tage.agent.main import TageAgent


class FakeMonitor:
    def __init__(self, *, fail_start=False):
        self.fail_start = fail_start
        self.closed = False

    def start(self, execution, *, observer):
        if self.fail_start:
            raise RuntimeError('start failed')

    async def aclose(self):
        self.closed = True


async def test_write_scope_requires_started_agent():
    agent = SimpleNamespace(_execution=None)
    with pytest.raises(RuntimeError, match='started TAGE agent'):
        async with TageAgent.observe_writes(agent):
            pass


async def test_nested_write_scope_fails_explicitly():
    agent = SimpleNamespace(_execution=object(), _write_observation_active=True)
    with pytest.raises(RuntimeError, match='already active'):
        async with TageAgent.observe_writes(agent):
            pass


async def test_write_scope_restores_flag_after_start_error():
    monitor = FakeMonitor(fail_start=True)
    agent = SimpleNamespace(_execution=object(), _write_observation_active=False, _write_monitor=monitor)
    with pytest.raises(RuntimeError, match='start failed'):
        async with TageAgent.observe_writes(agent):
            pass
    assert monitor.closed and not agent._write_observation_active


async def test_write_scope_closes_after_body_error():
    monitor = FakeMonitor()
    agent = SimpleNamespace(_execution=object(), _write_observation_active=False, _write_monitor=monitor)
    with pytest.raises(RuntimeError, match='body failed'):
        async with TageAgent.observe_writes(agent) as observations:
            assert observations == []
            raise RuntimeError('body failed')
    assert monitor.closed and not agent._write_observation_active
