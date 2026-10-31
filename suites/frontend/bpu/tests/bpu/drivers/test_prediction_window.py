"""Protocol driver tests on the existing Reactor memory backend, not a DUT."""
import asyncio

import pytest
from toffee import Bundle, Execution, MemoryBackend, XPhase, RisingEdge, on, XEvent, XEventKind

from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.bpu.driver.control import BpuControlDriver, PredictionWindow
from suites.frontend.bpu.ports.bindings import PortBinding
from tests.framework.fakes import Signal


def control_binding():
    clock = object()
    signals = dict(prediction_ready=Signal(width=1), meta_ready=Signal(width=1),
                   abtb_enable=Signal(width=1))
    return PortBinding(clock, Bundle(**signals), 'bpu.test-controls'), signals


@pytest.mark.parametrize('accepted', (1, 3, 5))
async def test_window_closes_on_actual_acceptance_count_not_a_fixed_duration(accepted):
    binding, signals = control_binding(); seen = []; receipts = []
    completed = asyncio.get_running_loop().create_future()
    def phase(phase, tick):
        if phase is XPhase.RISING_STABLE:
            seen.append((tick, signals['prediction_ready'].value))
    def capture(event):
        if signals['prediction_ready'].value:
            receipts.append(event)
            if len(receipts) == accepted:
                completed.set_result(event)
    async def delivered(_):
        pass
    backend = MemoryBackend(binding.clock, on_phase=phase)
    driver = BpuControlDriver(binding)
    values = dict(prediction_ready=0, meta_ready=1, abtb_enable=1)
    async with Execution(backend) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), delivery='lossless',
            capture=capture)(delivered).bind())
        try:
            async with driver:
                result = await driver.send(PredictionWindow(values, completed, 'actual-source-accepted', 16))
        finally:
            execution.reactor.cancel_subscription(subscription)
    assert len(receipts) == accepted and result is receipts[-1]
    assert sum(ready for _, ready in seen) == accepted
    assert seen[-1][1] == 0
    assert signals['meta_ready'].value == signals['abtb_enable'].value == 1
    assert values['prediction_ready'] == 0


async def test_timeout_closes_ready_and_preserves_other_controls():
    binding, signals = control_binding(); driver = BpuControlDriver(binding)
    completed = asyncio.get_running_loop().create_future()
    async with Execution(MemoryBackend(binding.clock)):
        async with driver:
            with pytest.raises(TimeoutError, match='missing-original'):
                await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1),
                    completed, 'missing-original', 3))
    assert not completed.done(), 'timing out a driver must not cancel its monitor receipt'
    assert signals['prediction_ready'].value == 0
    assert signals['meta_ready'].value == signals['abtb_enable'].value == 1


async def test_comparison_exception_is_not_swallowed_and_ready_still_closes():
    class Mismatch(AssertionError):
        pass
    error = Mismatch('original source no longer matches')
    completed = asyncio.get_running_loop().create_future()
    binding, signals = control_binding(); driver = BpuControlDriver(binding)
    async with Execution(MemoryBackend(binding.clock)):
        async with driver:
            with pytest.raises(Mismatch, match='original source'):
                await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1),
                    completed, 'compare', 3, failure=lambda: error))
    assert signals['prediction_ready'].value == 0


async def test_normal_persistent_controls_keep_the_existing_launch_contract():
    binding, signals = control_binding(); driver = BpuControlDriver(binding)
    async with Execution(MemoryBackend(binding.clock)):
        async with driver:
            result = await driver.send(dict(prediction_ready=1, meta_ready=1, abtb_enable=0))
    assert result.tick == 4 and signals['prediction_ready'].value == 1
    assert signals['abtb_enable'].value == 0


async def test_actual_on_capture_can_close_the_window_before_a_younger_acceptance():
    binding, signals = control_binding(); actual = []; captured = []
    completed = asyncio.get_running_loop().create_future()
    def phase(phase, tick):
        if phase is XPhase.RISING_STABLE and signals['prediction_ready'].value:
            actual.append(tick)
    def capture(event):
        if signals['prediction_ready'].value:
            captured.append(event.tick)
            if len(captured) == 3:
                completed.set_result(event)
    async def delivered(_):
        pass
    driver = BpuControlDriver(binding)
    async with Execution(MemoryBackend(binding.clock, on_phase=phase)) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), delivery='lossless',
            capture=capture)(delivered).bind())
        try:
            async with driver:
                result = await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1),
                    completed, 'captured-original', 16))
        finally:
            execution.reactor.cancel_subscription(subscription)
    assert len(actual) == len(captured) == 3
    assert result.tick == captured[-1]


@pytest.mark.parametrize('kwargs', ({'accepted': None}, {'name': ''}, {'timeout_cycles': 0},
                                  {'timeout_cycles': True}, {'failure': False}))
async def test_invalid_window_is_rejected_before_driving(kwargs):
    values = dict(values={}, accepted=asyncio.get_running_loop().create_future(), name='source', timeout_cycles=8)
    with pytest.raises(ValueError): PredictionWindow(**dict(values, **kwargs))


async def test_stale_acceptance_cannot_close_a_new_window():
    completed = asyncio.get_running_loop().create_future()
    completed.set_result(None)
    with pytest.raises(ValueError, match='fresh'):
        PredictionWindow({}, completed, 'stale')


@pytest.mark.parametrize('invalid', (None, XEvent(event_id=0, tick=-1, phase=XPhase.EXTERNAL,
                                               kind=XEventKind.EXTERNAL)))
async def test_external_completion_is_not_an_actual_acceptance(invalid):
    binding, signals = control_binding(); completed = asyncio.get_running_loop().create_future()
    def capture(event):
        if signals['prediction_ready'].value and not completed.done():
            completed.set_result(invalid)
    async def delivered(_):
        pass
    async with Execution(MemoryBackend(binding.clock)) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), delivery='lossless',
            capture=capture)(delivered).bind())
        try:
            async with BpuControlDriver(binding) as driver:
                with pytest.raises(TypeError, match='real rising-stable'):
                    await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), completed, 'invalid'))
        finally:
            execution.reactor.cancel_subscription(subscription)
    assert signals['prediction_ready'].value == 0


async def test_monitor_exception_is_propagated_and_ready_closes():
    binding, signals = control_binding(); completed = asyncio.get_running_loop().create_future()
    error = AssertionError('acceptance comparison failed')
    def capture(event):
        if signals['prediction_ready'].value and not completed.done():
            completed.set_exception(error)
    async def delivered(_):
        pass
    async with Execution(MemoryBackend(binding.clock)) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), delivery='lossless',
            capture=capture)(delivered).bind())
        try:
            async with BpuControlDriver(binding) as driver:
                with pytest.raises(AssertionError, match='acceptance comparison failed') as failure:
                    await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), completed, 'failed'))
                assert failure.value is error
        finally:
            execution.reactor.cancel_subscription(subscription)
    assert signals['prediction_ready'].value == 0


async def test_agent_closes_its_ready_shadow_after_window_failure():
    agent = object.__new__(BpuAgent)
    agent._started = True; agent._reset_vector = 0x40000000
    agent._prediction_ready, agent._meta_ready = 0, 0
    agent._predictor_enabled = {name: int(name in ('abtb','mbtb'))
        for name in ('ubtb','abtb','mbtb','tage','sc','ittage','ras')}
    sent = []
    class Driver:
        async def send(self, tx):
            sent.append(tx)
            raise AssertionError('original source failed')
    agent.control_driver = Driver()
    with pytest.raises(AssertionError, match='original source'):
        await agent.accept_predictions_until(asyncio.get_running_loop().create_future(), name='owned-source')
    assert agent._prediction_ready == 0 and agent._meta_ready == 1
    assert sent[0].values['mbtb_enable'] == sent[0].values['abtb_enable'] == 1
