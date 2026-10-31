"""The existing driver closes inverted windows on actual SDK transfers."""
import asyncio
from contextlib import suppress
import pytest
from toffee import Bundle, Execution, MemoryBackend, ReadyValid, ReadyValidMonitor, Role, XPhase, RisingEdge, DriveStable, on, XEvent, XEventKind
from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.bpu.driver.control import BpuControlDriver, PredictionWindow
from tests.bpu.drivers.test_prediction_window import control_binding
from tests.framework.fakes import Signal


async def scenario(count, *, deferred, schedule):
    binding, signals = control_binding()
    signals['prediction_ready'].value = 1
    physical = [1]
    receipt = asyncio.get_running_loop().create_future()
    prepared = asyncio.get_running_loop().create_future() if schedule else None
    ports = tuple(ReadyValid(clock=binding.clock, valid=Signal(1), ready=Signal(), bits=Bundle(value=Signal(width=8)),
                            role=Role.MONITOR, name=f'service-{o}') for o in range(2))
    monitors = tuple(ReadyValidMonitor(p, decoder=lambda d: d.value.as_int()) for p in ports)
    actual, compared = [[], []], [[], []]
    def phase(phase, tick):
        if phase is XPhase.FALLING_STABLE:
            level = physical[0] if deferred else signals['prediction_ready'].value
            for p in ports: p.ready.Set(1 - level)
        elif phase is XPhase.RISING_STABLE:
            for o, p in enumerate(ports):
                if p.ready.U():
                    actual[o].append(tick); p.bits.value.Set(len(actual[o]))
            # Match native XClock: the rising edge consumes OLD pins first;
            # pending rise writes reach the DUT only AFTER that edge.
            physical[0] = signals['prediction_ready'].value
    async def collect(o):
        while True:
            t = await monitors[o].recv()
            assert t.value == len(compared[o])
            compared[o].append(t.accepted_tick)
            if tuple(map(len, compared)) == (count, count):
                receipt.set_result(t.event)
    def prepare(event):
        if (prepared is not None and not prepared.done() and tuple(map(len, actual)) == (count - 1, count - 1)
                and all(p.valid.U() and p.ready.U() for p in ports)):
            prepared.set_result(event)
    async def delivered(_): pass
    async with Execution(MemoryBackend(binding.clock, on_phase=phase)) as execution:
        for monitor in monitors: monitor.start(execution)
        subscription = execution.subscribe(on(DriveStable(binding.clock), capture=prepare)(delivered).bind()) if schedule else None
        tasks = [asyncio.create_task(collect(o)) for o in range(2)]
        try:
            async with BpuControlDriver(binding) as driver:
                event = await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt,
                    'one-actual-service-pair', 16, prediction_ready=False, prepared=prepared))
        finally:
            if subscription is not None: execution.reactor.cancel_subscription(subscription)
            for task in tasks: task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError): await task
            for monitor in monitors: await monitor.aclose()
    return actual, compared, event, signals


@pytest.mark.parametrize('count', (1, 2, 3))
@pytest.mark.parametrize('deferred', (False, True))
async def test_read_pause_closes_after_exactly_the_compared_sdk_service_pairs(count, deferred):
    actual, compared, event, signals = await scenario(count, deferred=deferred, schedule=deferred)
    assert actual == compared and tuple(map(len, actual)) == (count, count)
    assert actual[0] == actual[1] and event.tick == actual[0][-1]
    assert signals['prediction_ready'].value == signals['meta_ready'].value == signals['abtb_enable'].value == 1


async def test_native_rise_write_without_preparation_reproduces_the_extra_physical_service():
    actual, _, event, _ = await scenario(1, deferred=True, schedule=False)
    assert tuple(map(len, actual)) == (2, 2)
    assert event.tick == actual[0][0] and actual[0] == actual[1]


async def test_prepared_candidate_without_actual_sdk_receipt_cannot_complete_window():
    binding, signals = control_binding(); receipt = asyncio.get_running_loop().create_future()
    prepared = asyncio.get_running_loop().create_future()
    def prepare(event):
        if not prepared.done(): prepared.set_result(event)
    async def delivered(_): pass
    async with Execution(MemoryBackend(binding.clock)) as execution:
        subscription = execution.subscribe(on(DriveStable(binding.clock), capture=prepare)(delivered).bind())
        try:
            async with BpuControlDriver(binding) as driver:
                with pytest.raises(TimeoutError):
                    await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt,
                        'missing-actual-service', 3, prediction_ready=False, prepared=prepared))
        finally: execution.reactor.cancel_subscription(subscription)
    assert prepared.done() and not receipt.done() and signals['prediction_ready'].value == 1


async def test_service_window_timeout_restores_prediction_and_does_not_cancel_monitor_receipt():
    binding, signals = control_binding(); receipt = asyncio.get_running_loop().create_future()
    async with Execution(MemoryBackend(binding.clock)):
        async with BpuControlDriver(binding) as driver:
            with pytest.raises(TimeoutError, match='missing-service'):
                await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt,
                    'missing-service', 3, prediction_ready=False))
    assert signals['prediction_ready'].value == 1 and not receipt.done()


async def test_service_window_failure_restores_prediction_and_keeps_first_comparison_error():
    binding, signals = control_binding(); receipt = asyncio.get_running_loop().create_future()
    error = AssertionError('partial pair has wrong identity')
    async with Execution(MemoryBackend(binding.clock)):
        async with BpuControlDriver(binding) as driver:
            with pytest.raises(AssertionError) as caught:
                await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt, 'wrong-service',
                    failure=lambda: error, prediction_ready=False))
    assert caught.value is error and signals['prediction_ready'].value == 1


@pytest.mark.parametrize('value', (0, 1, None, 'false'))
async def test_inverted_window_level_must_be_an_explicit_boolean(value):
    with pytest.raises(ValueError, match='boolean'):
        PredictionWindow({}, asyncio.get_running_loop().create_future(), 'invalid', prediction_ready=value)


async def test_agent_restores_its_public_control_shadow_after_service_window_failure():
    agent = object.__new__(BpuAgent); agent._started = True; agent._reset_vector = 0x40000000
    agent._prediction_ready, agent._meta_ready = 1, 0
    agent._predictor_enabled = {n: int(n in ('mbtb', 'tage')) for n in ('ubtb','abtb','mbtb','tage','sc','ittage','ras')}
    sent = []
    class Driver:
        async def send(self, tx):
            sent.append(tx); raise AssertionError('comparison failed')
    agent.control_driver = Driver()
    with pytest.raises(AssertionError, match='comparison failed'):
        await agent.allow_services_until(asyncio.get_running_loop().create_future(),
            prepared=asyncio.get_running_loop().create_future(), name='partial-pair')
    assert not sent[0].prediction_ready and agent._prediction_ready == agent._meta_ready == 1
    assert sent[0].values['mbtb_enable'] == sent[0].values['tage_enable'] == 1


async def test_agent_requires_preparation_before_any_service_control_write():
    agent = object.__new__(BpuAgent); agent._started = True
    agent._prediction_ready, agent._meta_ready = 1, 0
    accepted = asyncio.get_running_loop().create_future()
    with pytest.raises(TypeError, match='prepared'):
        await agent.allow_services_until(accepted, name='missing-preparation')
    with pytest.raises(ValueError, match='pre-edge'):
        await agent.allow_services_until(accepted, prepared=None, name='null-preparation')
    assert agent._prediction_ready == 1 and agent._meta_ready == 0 and not accepted.done()


@pytest.mark.parametrize('invalid', (None, XEvent(event_id=0, tick=-1, phase=XPhase.EXTERNAL, kind=XEventKind.EXTERNAL)))
async def test_service_window_needs_an_actual_acceptance_not_external_completion(invalid):
    binding, signals = control_binding(); receipt = asyncio.get_running_loop().create_future()
    def capture(_):
        if not receipt.done(): receipt.set_result(invalid)
    async def delivered(_): pass
    async with Execution(MemoryBackend(binding.clock)) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), capture=capture)(delivered).bind())
        try:
            async with BpuControlDriver(binding) as driver:
                with pytest.raises(TypeError, match='real rising-stable'):
                    await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt, 'invalid-service', prediction_ready=False))
        finally: execution.reactor.cancel_subscription(subscription)
    assert signals['prediction_ready'].value == 1


async def test_service_window_propagates_monitor_future_failure_and_resumes_prediction():
    binding, signals = control_binding(); receipt = asyncio.get_running_loop().create_future()
    error = AssertionError('SDK service belongs to another identity')
    def capture(_):
        if not receipt.done(): receipt.set_exception(error)
    async def delivered(_): pass
    async with Execution(MemoryBackend(binding.clock)) as execution:
        subscription = execution.subscribe(on(RisingEdge(binding.clock), capture=capture)(delivered).bind())
        try:
            async with BpuControlDriver(binding) as driver:
                with pytest.raises(AssertionError) as caught:
                    await driver.send(PredictionWindow(dict(meta_ready=1, abtb_enable=1), receipt, 'wrong-service', prediction_ready=False))
                assert caught.value is error
        finally: execution.reactor.cancel_subscription(subscription)
    assert signals['prediction_ready'].value == 1
