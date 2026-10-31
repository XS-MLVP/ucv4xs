from __future__ import annotations

import pytest
from toffee import ClockCycles
from toffee import Execution
from toffee import MemoryBackend

from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.ports.bindings import PortBinding
from tests.framework.fakes import Signal
from tests.framework.fakes import bundle_binding


@pytest.mark.feature("ENV-MON-001")
async def test_monitor_captures_immutable_timestamped_snapshot():
    interface, data = bundle_binding()
    interface.bits.drive({"data": 0x12})
    monitor = CycleMonitor(
        interface,
        decoder=lambda sample: sample.data.as_int(),
    )

    async with Execution(MemoryBackend(interface.clock)) as execution:
        monitor.start(execution)
        await ClockCycles(interface.clock, 1)
        observation = await monitor.recv()
        interface.bits.drive({"data": 0x34})
        await monitor.aclose()

    assert observation.event.tick == 2
    assert observation.value == 0x12


@pytest.mark.feature("ENV-MON-002")
async def test_monitor_can_close_and_rearm():
    interface, data = bundle_binding()
    monitor = CycleMonitor(
        interface,
        decoder=lambda sample: sample.data.as_int(),
    )

    async with Execution(MemoryBackend(interface.clock)) as execution:
        interface.bits.drive({"data": 1})
        monitor.start(execution)
        await ClockCycles(interface.clock, 1)
        assert (await monitor.recv()).value == 1
        await monitor.aclose()

        interface.bits.drive({"data": 2})
        monitor.start(execution)
        await ClockCycles(interface.clock, 1)
        assert (await monitor.recv()).value == 2
        await monitor.aclose()


@pytest.mark.feature("ENV-MON-002")
async def test_lossless_monitor_overflow_fails_execution():
    interface, _ = bundle_binding()
    monitor = CycleMonitor(interface, capacity=1)

    with pytest.raises(RuntimeError, match="monitor queue overflow"):
        async with Execution(MemoryBackend(interface.clock)) as execution:
            monitor.start(execution)
            try:
                await ClockCycles(interface.clock, 3)
            finally:
                # Native monitors retain delivery failures and surface them to
                # recv()/aclose(); the owner must close its components.
                await monitor.aclose()


@pytest.mark.feature("ENV-MON-001")
async def test_monitor_can_sample_scalar_without_bundle():
    clock = object()
    data = Signal(width=8)
    data.Set(0x34)
    monitor = CycleMonitor(
        PortBinding(clock, data, "scalar"),
        decoder=lambda sample: sample.as_int(),
    )

    async with Execution(MemoryBackend(clock)) as execution:
        monitor.start(execution)
        await ClockCycles(clock, 1)
        observation = await monitor.recv()
        await monitor.aclose()

    assert observation.value == 0x34


@pytest.mark.parametrize('callback', [False, True])
async def test_rebinding_recompiles_sampler_and_preserves_old_snapshots(callback):
    binding, data = bundle_binding()
    other, other_data = bundle_binding(clock=binding.clock)
    data.Set(0x12)
    other_data.Set(0x34)
    monitor = CycleMonitor(binding, decoder=lambda sample: sample.data.as_int())
    observations = []
    async with Execution(MemoryBackend(binding.clock)) as execution:
        monitor.start(execution, observer=observations.append if callback else None)
        await ClockCycles(binding.clock, 1)
        first = observations[-1] if callback else await monitor.recv()
        monitor.binding = other
        monitor.decoder = lambda sample: sample.data.as_int() + 1
        await ClockCycles(binding.clock, 1)
        second = observations[-1] if callback else await monitor.recv()
        monitor.binding = binding
        await ClockCycles(binding.clock, 1)
        third = observations[-1] if callback else await monitor.recv()
        await monitor.aclose()
    assert (first.value, second.value, third.value) == (0x12, 0x35, 0x13)
    assert (first.event.tick, second.event.tick, third.event.tick) == (2, 4, 6)
