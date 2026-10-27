"""Pure lifecycle checks for public writer substitution and state observation."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
import pytest

from bpuverify.abtb.agent.main import AbtbAgent
from bpuverify.abtb.env.state.session import StateObservation


class OriginalDriver:
    def __init__(self):
        self.closed, self.restored = 0, 0

    def close(self):
        self.closed += 1

    async def __aenter__(self):
        self.restored += 1
        return self


class ReplacementDriver:
    def __init__(self, binding, *, enter_error=False, exit_error=False):
        self.binding, self.enter_error, self.exit_error = binding, enter_error, exit_error
        self.entered, self.exited, self.primary = 0, 0, None

    async def __aenter__(self):
        self.entered += 1
        if self.enter_error:
            raise RuntimeError('driver-enter-failure')
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited += 1
        self.primary = exc
        if self.exit_error:
            raise RuntimeError('driver-exit-failure')


def agent_stub():
    agent = AbtbAgent.__new__(AbtbAgent)
    agent._started, agent._execution, agent._training_override = True, object(), None
    agent.ports = SimpleNamespace(training=object())
    agent.training_driver = OriginalDriver()
    return agent


@pytest.mark.parametrize('failure', ('none','body','enter','exit'))
async def test_original_writer_restored_on_every_exit_path(failure):
    agent = agent_stub()
    original = agent.training_driver
    driver = ReplacementDriver(agent.ports.training, enter_error=failure=='enter', exit_error=failure=='exit')
    async def use():
        async with agent.using_training_driver(driver):
            assert agent.training_driver is driver
            if failure == 'body':
                raise RuntimeError('body-failure')
    if failure == 'none':
        await use()
    else:
        with pytest.raises(RuntimeError, match=failure+'-failure' if failure=='body' else 'driver-'+failure+'-failure'):
            await use()
    assert agent.training_driver is original and agent._training_override is None
    assert original.closed == original.restored == 1
    assert driver.entered == 1
    assert driver.exited == int(failure != 'enter')
    assert (driver.primary is not None) == (failure == 'body')


async def test_nested_writer_substitution_does_not_release_active_owner():
    agent = agent_stub()
    original = agent.training_driver
    first, second = (ReplacementDriver(agent.ports.training) for _ in range(2))
    async with agent.using_training_driver(first):
        with pytest.raises(RuntimeError, match='already replaced'):
            async with agent.using_training_driver(second):
                pytest.fail('nested owner was accepted')
        assert agent.training_driver is first and second.entered == 0
    assert agent.training_driver is original and original.restored == 1


async def test_foreign_port_rejected_without_releasing_original_writer():
    agent = agent_stub()
    with pytest.raises(ValueError, match='this training port'):
        async with agent.using_training_driver(ReplacementDriver(object())):
            pytest.fail('foreign port was accepted')
    assert agent.training_driver.closed == agent.training_driver.restored == 0


def test_execution_is_only_available_on_an_active_agent():
    agent = agent_stub()
    assert agent.execution is agent._execution
    agent._started = False
    with pytest.raises(RuntimeError, match='active Execution'):
        _ = agent.execution


@pytest.mark.parametrize('failure', ('none','monitor-start','reset','checker','body'))
async def test_state_session_closes_monitor_and_restores_driver_after_setup_or_body_failure(failure):
    calls = []
    class Agent:
        execution = object()
        async def reset(self):
            calls.append('reset')
            if failure == 'reset':
                raise RuntimeError(failure)
        @asynccontextmanager
        async def using_training_driver(self, driver):
            calls.append('driver-enter')
            try:
                yield driver
            finally:
                calls.append('driver-exit')
    class Monitor:
        def start(self, execution, *, observer):
            calls.append('monitor-start')
            if failure == 'monitor-start':
                raise RuntimeError(failure)
        async def aclose(self):
            calls.append('monitor-close')
    class Checker:
        def capture(self, observation):
            pass
        def raise_failure(self):
            calls.append('checker')
            if failure == 'checker':
                raise RuntimeError(failure)
    session = StateObservation(Agent(), Monitor(), Checker(), driver=object())
    async def use():
        async with session:
            if failure == 'body':
                raise RuntimeError(failure)
    if failure == 'none':
        await use()
    else:
        with pytest.raises(RuntimeError, match=failure):
            await use()
    assert calls[-1] == 'monitor-close' and session._stack is None
    assert calls.count('driver-exit') == int(failure != 'monitor-start')
