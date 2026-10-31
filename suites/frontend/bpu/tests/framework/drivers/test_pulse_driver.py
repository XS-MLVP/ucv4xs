from __future__ import annotations

import pytest
from toffee import Execution
from toffee import MemoryBackend
from toffee import XPhase

from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.drivers.signal import PulseDriver
from tests.framework.fakes import Signal
from tests.framework.fakes import pulse_binding


@pytest.mark.feature("ENV-DRV-002")
async def test_pulse_is_visible_for_exactly_one_accepting_cycle():
    clock = object()
    interface, valid, data = pulse_binding(clock=clock)
    rising_samples: list[tuple[int, int, int]] = []
    backend = MemoryBackend(
        clock,
        on_phase=lambda phase, tick: rising_samples.append(
            (tick, valid.value, data.value)
        )
        if phase is XPhase.RISING_STABLE
        else None,
    )
    driver = PulseDriver(interface)

    async with Execution(backend):
        completed = await driver.send({"data": 0xA5})
        driver.close()

    assert completed.tick == 4
    assert rising_samples == [(2, 1, 0xA5), (4, 0, 0xA5)]


@pytest.mark.feature("ENV-DRV-002")
async def test_pulse_driver_can_drive_scalar_payload():
    clock = object()
    valid = Signal()
    data = Signal(width=8)
    driver = PulseDriver(PulseBinding(clock, valid, data, "scalar_pulse"))

    async with Execution(MemoryBackend(clock)):
        await driver.send(0xA5)
        driver.close()

    assert valid.value == 0
    assert data.value == 0xA5


@pytest.mark.feature("ENV-DRV-002")
async def test_pulse_burst_keeps_valid_high_on_adjacent_beats():
    clock = object()
    interface, valid, data = pulse_binding(clock=clock)
    rising_samples: list[tuple[int, int, int]] = []
    backend = MemoryBackend(
        clock,
        on_phase=lambda phase, tick: rising_samples.append(
            (tick, valid.value, data.value)
        )
        if phase is XPhase.RISING_STABLE
        else None,
    )
    driver = PulseDriver(interface)

    async with Execution(backend):
        completed = await driver.send_many(({"data": 0xA5}, {"data": 0x5A}))
        driver.close()

    assert completed.tick == 6
    assert rising_samples == [(2, 1, 0xA5), (4, 1, 0x5A), (6, 0, 0x5A)]
