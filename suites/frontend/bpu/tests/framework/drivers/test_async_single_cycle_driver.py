from __future__ import annotations

import asyncio

import pytest
from toffee import AsyncSingleCycleDriver as CoreAsyncSingleCycleDriver
from toffee import Execution
from toffee import MemoryBackend
from toffee import TransferState

from bpuverify.common.driver.signal import AsyncSingleCycleDriver
from bpuverify.common.bundle.bindings import PortBinding
from tests.framework.fakes import Signal
from tests.framework.fakes import bundle_binding


@pytest.mark.feature("ENV-DRV-003")
async def test_async_single_cycle_driver_accepts_requests_on_adjacent_cycles():
    interface, _ = bundle_binding()
    driver = AsyncSingleCycleDriver(
        interface,
        idle={"data": 0},
        encoder=lambda value: {"data": value},
    )
    assert isinstance(driver, CoreAsyncSingleCycleDriver)

    async with Execution(MemoryBackend(interface.clock)) as execution:
        driver.start(execution)
        submitted = [driver.submit(value) for value in (0x11, 0x22, 0x33)]
        accepted = [await driver.recv_accepted() for _ in submitted]

        assert accepted == submitted
        assert [item.accepted_event.tick for item in accepted] == [2, 4, 6]
        assert all(item.state is TransferState.PROCESSING for item in accepted)
        for item in accepted:
            item.complete(item.accepted_event, None)
        await driver.aclose()

    assert all(item.state is TransferState.COMPLETED for item in submitted)


@pytest.mark.feature("ENV-DRV-004")
async def test_async_single_cycle_queue_full_and_close_are_explicit():
    interface, _ = bundle_binding()
    driver = AsyncSingleCycleDriver(
        interface,
        idle={"data": 0},
        capacity=1,
    )

    async with Execution(MemoryBackend(interface.clock)) as execution:
        driver.start(execution)
        queued = driver.submit({"data": 1})
        with pytest.raises(RuntimeError, match="submission capacity is full"):
            driver.submit({"data": 2})
        await driver.aclose()

    assert queued.state is TransferState.CANCELLED
    with pytest.raises(asyncio.CancelledError):
        await queued


@pytest.mark.feature("ENV-DRV-003")
async def test_async_single_cycle_driver_can_queue_scalar_signals_without_bundle():
    clock = object()
    data = Signal(width=8)
    driver = AsyncSingleCycleDriver(PortBinding(clock, data, "scalar"), idle=0)

    async with Execution(MemoryBackend(clock)) as execution:
        driver.start(execution)
        transfers = [driver.submit(value) for value in (1, 2)]
        accepted = [await driver.recv_accepted() for _ in transfers]
        assert accepted == transfers
        assert [item.accepted_event.tick for item in accepted] == [2, 4]
        for item in accepted:
            item.complete(item.accepted_event, None)
        await driver.aclose()
