from __future__ import annotations

import pytest
from toffee import Execution
from toffee import MemoryBackend
from toffee import XPhase

from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.ports.bindings import PortBinding
from tests.framework.fakes import Signal
from tests.framework.fakes import bundle_binding


@pytest.mark.feature("ENV-DRV-001")
async def test_driver_ownership_conflicts_and_releases():
    interface, _ = bundle_binding()
    first = ClockedWriteDriver(interface)
    second = ClockedWriteDriver(interface)

    async with Execution(MemoryBackend(interface.clock)):
        await first.__aenter__()
        with pytest.raises(RuntimeError, match="already have a driver"):
            await second.__aenter__()

        first.close()
        await second.__aenter__()
        second.close()


@pytest.mark.feature("ENV-DRV-001")
async def test_driver_rejects_dut_output():
    interface, _ = bundle_binding(direction="output")
    driver = ClockedWriteDriver(interface)

    async with Execution(MemoryBackend(interface.clock)):
        with pytest.raises(ValueError, match="cannot drive DUT outputs"):
            await driver.__aenter__()


@pytest.mark.feature("ENV-IF-002")
async def test_clocked_write_driver_hides_rise_write_launch_cycle():
    clock = object()
    interface, data = bundle_binding(clock=clock)
    rising_samples: list[tuple[int, int]] = []
    backend = MemoryBackend(
        clock,
        on_phase=lambda phase, tick: rising_samples.append((tick, data.value))
        if phase is XPhase.RISING_STABLE
        else None,
    )
    driver = ClockedWriteDriver(interface)

    async with Execution(backend):
        completed = await driver.send({"data": 0x5A})
        driver.close()

    assert completed.tick == 4
    assert rising_samples == [(2, 0x5A), (4, 0x5A)]


@pytest.mark.feature("ENV-DRV-001")
async def test_clocked_write_driver_can_drive_a_scalar_without_bundle():
    clock = object()
    data = Signal(width=8)
    driver = ClockedWriteDriver(PortBinding(clock, data, "scalar"))

    async with Execution(MemoryBackend(clock)):
        await driver.send(0x5A)
        driver.close()

    assert data.value == 0x5A
